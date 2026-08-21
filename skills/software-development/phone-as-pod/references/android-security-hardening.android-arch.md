# Android Security Hardening — EncryptedSharedPreferences + KeyStore fallback

Worked on `mazemaker-mobile` PreferencesManager.kt / AuthManager.kt. Durable
techniques for hardening secret storage in a Kotlin/Android app.

## Pattern: migrate secrets out of plaintext DataStore into EncryptedSharedPreferences

A DataStore (Preferences) file is PLAINTEXT on disk. Tokens/certs stored there
are readable. Migrate them to EncryptedSharedPreferences (AndroidX
`security-crypto`), which wraps values with an AndroidKeyStore-backed AES key.

Standard encrypted-store creation:

```kotlin
private val gatewaySecrets: android.content.SharedPreferences by lazy {
    val masterKey = MasterKey.Builder(context.applicationContext)
        .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
        .build()
    EncryptedSharedPreferences.create(
        context.applicationContext,
        "mazemaker_gateway_secrets",
        masterKey,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )
}
```

### PITFALL 1 — declare the type as `SharedPreferences`, NOT `EncryptedSharedPreferences`

`EncryptedSharedPreferences.create(...)` has a STATIC return type of
`SharedPreferences` (the `EncryptedSharedPreferences` interface is returned
internally). With a `by lazy` delegate, the delegate's `getValue` is resolved
from the lambda's inferred type. Declaring the property as
`EncryptedSharedPreferences` fails to compile:

```
Property delegate must have a 'getValue' method. None of the following functions is suitable:
public inline operator fun <T> Lazy<SharedPreferences>.getValue(thisRef: Any?, property: KProperty<*>): SharedPreferences
```

Fix: type the property `android.content.SharedPreferences`. All you need
(`getString`/`edit().putString(...).apply()`/`edit().clear().apply()`) is on
`SharedPreferences` anyway.

### PITFALL 2 — `Flow.firstOrNull()` is a SUSPEND function

The naive "fall back to DataStore for migration" read inside a
`context.dataStore.data.map { ... }` transform fails to compile:

```
Suspend function 'firstOrNull' should be called only from a coroutine or another suspend function
```

`map`'s lambda is NOT suspend, so you cannot block on a Flow there. Fix: the
`map` lambda already has the current `Preferences` (`p`); pass the already-read
value in:

```kotlin
fun getGatewayConfig(): Flow<GatewayConfig> = context.dataStore.data.map { p ->
    GatewayConfig(
        token   = gatewaySecret(GATEWAY_TOKEN, p[GATEWAY_TOKEN]) ?: "",
        certPem = gatewaySecret(GATEWAY_CERT, p[GATEWAY_CERT])?.takeIf { it.isNotBlank() },
        // ...
    )
}

/** Prefer encrypted store; on legacy install read + persist from the plaintext DataStore value. */
private fun gatewaySecret(key: Preferences.Key<String>, legacy: String?): String? {
    val encrypted = gatewaySecrets.getString(key.name, null)
    if (!encrypted.isNullOrBlank()) return encrypted
    if (!legacy.isNullOrBlank()) {
        val migrated = legacy.trim()
        gatewaySecrets.edit().putString(key.name, migrated).apply()
        return migrated
    }
    return null
}
```

Reuse the DataStore `stringPreferencesKey(...)` constants; `Preferences.Key` has
a `.name` field that equals the plaintext key string, so you write/read the
encrypted store with `key.name`.

### Migration bookkeeping
- `setGatewayConfig(...)`: write the secret to the encrypted store AND
  `p.remove(GATEWAY_TOKEN)` etc. in the DataStore edit, so the plaintext copy is
  dropped once the source of truth moves. Non-secret fields (enabled/host) stay
  in the DataStore.
- `clearAll()`: also `gatewaySecrets.edit().clear().apply()` — the DataStore
  `it.clear()` no longer touches the secrets.
- The stale plaintext copy left by the read-time migration is dropped on the
  next write; that is acceptable (read-time DataStore edits are re-entrant and
  best avoided).

## Pattern: KeyStore fallback so the app doesn't crash

`EncryptedSharedPreferences.create` / `MasterKey.Builder.build()` can throw when
the AndroidKeyStore is unavailable or corrupted (some devices). If it throws on
every auth-interceptor call, the app crashes. Wrap creation in try/catch and
fall back to plain `SharedPreferences`:

```kotlin
class AuthManager(context: Context) {
    private val isEncrypted: Boolean
    private val prefs: android.content.SharedPreferences
    init {
        var encrypted = true
        var store: android.content.SharedPreferences? = null
        try {
            val masterKey = MasterKey.Builder(context).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build()
            store = EncryptedSharedPreferences.create(context, "mazemaker_auth", masterKey,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM)
        } catch (e: Exception) {
            Log.w("AuthManager", "EncryptedSharedPreferences unavailable (${e::class.simpleName}: ${e.message}); " +
                "falling back to plain SharedPreferences", e)
            encrypted = false
            store = context.getSharedPreferences("mazemaker_auth_fallback", Context.MODE_PRIVATE)
        }
        isEncrypted = encrypted
        prefs = store!!
    }
}
```

Catch broad `Exception` (covers `SecurityException` and KeyStore/GeneralSecurity
wrappers). Keep the public method signatures identical; only the backing store
changes. Same idea as the Huawei TEE EC fallback in the main skill (pitfall 9).

## Verifying a Kotlin change (Android/Gradle — no package.json)

- Correct verification is the Gradle Kotlin compile task, NOT an npm-style test:
  ```bash
  export ANDROID_HOME=/home/alca/Android/Sdk        # read sdk.dir from android/local.properties
  cd android && ./gradlew :app:compileDebugKotlin
  ```
  Exit 0 = verified. This surfaces the exact compiler errors above.
- `--offline` fails if AndroidX deps aren't cached ("No cached version of
  androidx.security:security-crypto:... available for offline mode"). Drop
  `--offline` to let Gradle resolve (requires network).
- The harmless `SDK XML version 4 ... warning` on newer cmdline-tools is
  ignorable.
