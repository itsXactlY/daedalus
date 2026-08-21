# Telekom MagentaTV Multicast-Adressen (Stand 2026)

Die genauen IPs können je nach Region und Angebot variieren.      
Diese Liste dient als Ausgangspunkt zum Testen.

## Bekannte Multicast-IPs + Ports

| Multicast-IP | Port(s) | Typ |
|---|---|---|
| 239.100.1.1 | 5000 | Erste HD-Sender (ARD, ZDF, RTL etc.) |
| 239.100.1.2 | 5000 | |
| 239.100.100.1 | 5000 | |
| 239.35.0.1 | 1234 | Ältere Streams |
| 239.35.0.2 | 1234 | |
| 239.255.0.1 | 5000 | Backup/alternative Streams |
| 239.255.0.2 | 5001 | |

## Bereich

Telekom MagentaTV nutzt den Bereich `239.0.0.0/8`,        
Schwerpunkt auf `239.35.0.0/16` und `239.100.0.0/16`.

## Scan-Methode

Falls keine konkrete IP bekannt ist, kann der Bereich grob gescannt werden     
(sofern CAP_NET_RAW + IGMP-Proxy aktiv):

```bash
for ip in 239.100.{1..10}.{1..10}; do
  for port in 5000 5001 1234; do
    timeout 1 cvlc udp://@$ip:$port 2>/dev/null &
  done
done
```

Praktischer: Einen laufenden Telekom-Receiver (MagentaTV-Box) abwarten und dann     
per tcpdump die genutzte Multicast-IP ermitteln, die er joint.
