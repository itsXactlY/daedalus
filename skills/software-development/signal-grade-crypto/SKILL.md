---
name: signal-grade-crypto
description: Implement Signal-grade E2E encryption (X3DH + Double Ratchet + Safety Numbers) in Python with pycryptodome. Covers common pitfalls, server-mediated key exchange, and backward-compatible upgrades.
category: software-development
---

# Signal-Grade Crypto Implementation

Implement X3DH key agreement, Double Ratchet forward secrecy, Safety Numbers, and one-time prekeys in Python using pycryptodome (P-256 ECC + AES-256-GCM + HKDF-SHA256).

## Primitives

```python
from Crypto.PublicKey import ECC
from Crypto.Cipher import AES

def _ecc_generate():
    key = ECC.generate(curve='P-256')
    return key, key.export_key('DER'), key.public_key().export_key('DER')

def _ecdh_full(priv_key, pub_key) -> bytes:
    """64-byte shared point (x||y) for X3DH concatenation."""
    shared = pub_key.pointQ * priv_key.d
    return int(shared.x).to_bytes(32, 'big') + int(shared.y).to_bytes(32, 'big')

def hkdf_derive(ikm, length=32, salt=None, info=b""):
    if salt is None: salt = b'\x00' * 32
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    t, okm = b"", b""
    for i in range(1, (length + 31) // 32 + 1):
        t = hmac.new(prk, t + info + bytes([i]), hashlib.sha256).digest()
        okm += t
    return okm[:length]
```

## X3DH Key Agreement

### Key Bundle Structure
- **Identity Key (IK)**: Long-term ECDH P-256 keypair
- **Signed Prekey (SPK)**: Medium-term, signed by IK (HMAC of SPK_pub with IK_priv)
- **One-Time Prekeys (OPK)**: Ephemeral, consumed once, stored on server

### X3DH Computation
```
DH1 = DH(IK_A, SPK_B)    — Alice's identity with Bob's signed prekey
DH2 = DH(EK_A, IK_B)     — Alice's ephemeral with Bob's identity
DH3 = DH(EK_A, SPK_B)    — Alice's ephemeral with Bob's signed prekey
DH4 = DH(EK_A, OPK_B)    — Alice's ephemeral with Bob's one-time prekey (optional)

shared_secret = HKDF(DH1 || DH2 || DH3 || [DH4], info="jrwl-x3dh-v1")
```

**IMPORTANT**: Use `_ecdh_full` (x||y concatenation), NOT just x-coordinate. The x-only approach loses entropy and doesn't match the Signal spec.

### PITFALL: Server-Mediated OPK Management

When the server handles both sides of X3DH (single-server architecture):
1. The bundle endpoint must **save consumed OPK private keys** temporarily before deleting from the prekey store
2. The exchange endpoint uses stored OPK priv to compute the responder's side
3. Without this, the consumed OPK's private key is lost and Bob can't reconstruct the shared secret

```python
# In bundle endpoint:
opk = consume_prekey(their_id)
auth_manager._consumed_opks[opk['id']] = opk['priv']  # SAVE BEFORE LOST!

# In exchange endpoint:
opk_priv = auth_manager._consumed_opks.get(opk_id)
shared_secret = x3dh_respond(ik_b_priv, spk_b_priv, opk_priv, ik_a_pub, ek_a_pub)
```

## Double Ratchet

### Initialization Symmetry — CRITICAL PITFALL

Both sides MUST derive their initial chain keys identically:

```python
# CORRECT — both sides use same HKDF params:
if is_initiator:
    self.send_chain_key = hkdf_derive(shared_secret, info=b"jrwl-init-chain-v1")
else:
    self.recv_chain_key = hkdf_derive(shared_secret, info=b"jrwl-init-chain-v1")

# WRONG — different derivation causes MAC check failure:
if is_initiator:
    self.send_chain_key = hkdf_derive(shared_secret, info=b"jrwl-init-chain-v1")
else:
    # This includes DH output, Alice doesn't → MISMATCH!
    self.recv_chain_key = hkdf_derive(shared_secret + dh_out, info=b"jrwl-recv-init-v1")
```

### First DH Pub Exchange — CRITICAL PITFALL

The responder needs the initiator's first ratchet DH public key **before** receiving the first message:

```python
# CORRECT:
ratchet_a = DoubleRatchet(ss, is_initiator=True)  # generates DH keypair
alice_first_dh_pub = ratchet_a._dh_pub_der
ratchet_b = DoubleRatchet(ss, is_initiator=False, their_ratchet_pub=alice_first_dh_pub)

# WRONG — Bob doesn't know Alice's DH pub:
ratchet_b = DoubleRatchet(ss, is_initiator=False)  # their_ratchet_pub=None
# → Bob's decrypt sees different DH pub → spurious ratchet step → MAC fail
```

### DH Ratchet Step — CRITICAL PITFALL

When ratcheting for send, use the **NEW** DH key, not the old one:

```python
# CORRECT — generate new key, then use it:
def _ratchet_for_send(self):
    their_pub = _ecc_import_pub(self.their_ratchet_pub_der)
    self._dh_key, self._dh_priv_der, self._dh_pub_der = _ecc_generate()  # NEW first
    dh_out = _ecdh_full(self._dh_key, their_pub)  # NEW key for DH
    rk_bytes = hkdf_derive(self.root_key + dh_out, length=64, info=b"jrwl-rk-v1")
    self.root_key, self.send_chain_key = rk_bytes[:32], rk_bytes[32:]

# WRONG — use old key then generate new:
def _ratchet_for_send(self):
    dh_out = _ecdh_full(self._dh_key, their_pub)  # OLD key → Alice can't match
    self._dh_key, ... = _ecc_generate()  # too late
```

**Why**: When Alice receives Bob's reply, she uses her OLD DH key with Bob's NEW DH pub. If Bob used his OLD key, Alice would need Bob's OLD pub (which she doesn't have). With the correct approach: `DH(Bob_new, Alice_old) == DH(Alice_old, Bob_new)` ✓

### Ratchet State Flow

```
Alice (initiator):                          Bob (responder):
send_chain = HKDF(ss)                       recv_chain = HKDF(ss)
  ↓ encrypt(msg1, send_chain[0])              ↓ decrypt(msg1, recv_chain[0])
  ↓ [includes Alice_DH_pub_a]                  ↓ their_dh_pub = Alice_DH_pub_a
                                               ↓ send_chain = None
recv_chain = None                             ↓ _ratchet_for_send():
                                               ↓   generate Bob_DH_pub_b
                                               ↓   DH(Bob_DH_new, Alice_DH_pub_a)
                                               ↓   send_chain = HKDF(ss || dh_out)
decrypt(msg2):                                encrypt(msg2, send_chain[0]):
  their_dh_pub = Bob_DH_pub_b                 ↓ [includes Bob_DH_pub_b]
  _ratchet_for_recv(Bob_DH_pub_b):
    DH(Alice_DH_old, Bob_DH_pub_b)
    recv_chain = HKDF(ss || dh_out)
  decrypt(msg2, recv_chain[0])  ← MATCHES
```

## Safety Numbers

```python
def safety_number(pub_a, pub_b, name_a="", name_b=""):
    if pub_a > pub_b:
        pub_a, pub_b = pub_b, pub_a
        name_a, name_b = name_b, name_a
    combined = name_a.encode() + pub_a + name_b.encode() + pub_b
    h = hashlib.sha512(combined).digest()
    hex_str = h[:30].hex().upper()  # 60 chars
    return ' '.join(hex_str[i:i+5] for i in range(0, 60, 5))
```

Sort by public key to ensure both parties compute the same number regardless of order.

## Server-Mediated Exchange (Gateway Pattern)

For single-server architectures where the gateway holds all keys:

1. **Identity creation**: Generate X3DH bundle + 10 OPKs, store OPKs to disk
2. **Bundle fetch**: `POST /api/x3dh/bundle` — consumes one OPK, stores its priv temporarily
3. **X3DH exchange**: `POST /api/x3dh/exchange` — computes both sides, creates ratchet sessions
4. **Message send**: Try `ratchet_encrypt()` first, fall back to legacy `encrypt_message()`
5. **Capture first DH pub**: After creating Alice's ratchet, grab `ratchet._dh_pub_der` and pass to Bob's constructor

## Backward Compatibility

Keep all original functions working with identical signatures. New features are additive:
- Legacy: `encrypt_message(plaintext, shared_secret)` / `decrypt_message(ciphertext, shared_secret)`
- New: `ratchet_encrypt(my_id, their_id, plaintext)` / `ratchet_decrypt(my_id, their_id, msg)`

## Verification

Always run a comprehensive self-test covering:
- Legacy ECDH roundtrip
- X3DH with and without OPK
- Double Ratchet encrypt → decrypt → reply → decrypt
- Multiple sequential messages
- Ratchet state serialization/deserialization
- Safety number determinism and order-independence
- Prekey consume/count lifecycle
