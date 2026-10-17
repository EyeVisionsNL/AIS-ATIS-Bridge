# First steps
## Meet your Bridge
The dashboard puts receiver controls, recent transmissions, validated ATIS and updates together. Start with the receiver panel, then work your way across.

![AIS-ATIS Bridge dashboard with example settings and recordings](https://raw.githubusercontent.com/EyeVisionsNL/AIS-ATIS-Bridge/main/images/dashboard.jpg)

*This project screenshot contains demonstration recordings and illustrative settings, not live reception. Click it to enlarge.*

## Get your first signal
1. In **Receiver**, select the second RTL-SDR. Leave AIS-catcher’s dongle to AIS-catcher.
2. Choose **Fixed channel** and select a marine voice channel active in your area, or choose **Scan channels** and enable a small selection.
3. Start with **Smart Gain** and **Automatic (noise tracking)** squelch.
4. Click **Save and start** and check the receiver status.
5. Click **Audio: off** to listen, then adjust **Volume**.

Sound comes from the device running your browser. There is no need to plug headphones into the Pi when you are browsing from your laptop.

## Let a transmission finish
Recent recordings become available for replay after the signal ends. A validated ATIS identity appears only when a suitable ATIS transmission is successfully decoded; ordinary speech alone does not identify a ship.

## Find the vessel
A fresh, unique AIS match enables **Show on AIS map**. If no match appears, use [[ATIS and AIS]] to understand the checks.

Ready to explore? [[Receiver and channels]] explains scanning and RF settings, and [[Audio and recordings]] covers listening and replay.
