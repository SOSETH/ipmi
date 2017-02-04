# Role: ipmi

Configuration of Serial-over-LAN for VSOS use.
We configure SOL with the specified baud rate(115200 per default) on the specific serial port (ttyS1 per default) and enable output of kernel messages and getty on this device. This is done by changing the CMDLINE in the default GRUB configuration!
Usage on a new hosts requires manual setup:
* Enter BIOS and make sure IPMI is activated and reachable
* While you're at it, some boards also support BIOS via SOL, so enable it if this is the case
* Enable SOL. Note the serial Port (COM3 = ttyS2)
* Make sure to override the defaults with their host-specific values if your configuration isn't COM2/ttyS1 and 115200 baud

On some host with very specific configurations(feel free to debug this), systemd will try to set up the serial console way to early in the boot process. You can verify this by removing "quiet" from the cmdline, the boot will take over 3000 seconds... If this is the case, you can set sol_enable_systemd to false, which will work around this by removing the kernel flag and starting a getty instance manually. Unfortunately this hides the dmesg :(
