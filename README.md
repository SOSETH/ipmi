# Role: ipmi

Configure IPMIs and Serial-over-LAN

## Configuration
|Variable|Default vaule|Description|
|--------|-------------|-----------|
| `sol_baudrate` | `115200` | |
| `sol_port` | `ttyS1` | |
| `sol_port_no` | `1` | |
| `sol_data_bits` | `8` | |
| `sol_parity_bits` | `n` | |
| `sol_partiy_bits_grub` | `"no"` | |
| `sol_stop_bits` | `1` | |
| `sol_flow_control` | `r` | |

Example IPMI network/user settings:

```
ipmiconfig:
  lan:
    channel: 1
    ip: 172.0.0.2
    gateway: 172.0.0.1
    netmask: 255.255.255.0
  users:
    - name: ADMIN
      password: ADMIN
      privileges: Administrator
      channel: 1
```

Usage on a new hosts requires manual setup:
* Enter BIOS and make sure IPMI is activated and reachable
* While you're at it, some boards also support BIOS via SOL, so enable it if this is the case
* Enable SOL. Note the serial Port (COM3 = ttyS2)
* Make sure to override the defaults with their host-specific values if your configuration isn't COM2/ttyS1 and 115200 baud


**Compatibility tested with:**
  * Debian 9
  * Debian 10

## License
GPLv3
