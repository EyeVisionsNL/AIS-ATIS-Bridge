# Receiver and channels
## One receiver, one job
Select the dongle dedicated to marine voice. The Bridge requires an explicit receiver selection; AIS-catcher retains exclusive ownership of its own dongle.

## Fixed channel or scan?
| Mode | What it does | A useful starting point |
| --- | --- | --- |
| Fixed channel | Stays on your selected channel | Checking a known local voice channel |
| Scan channels | Scans the channels you enable | Following several nearby marine channels |

Enable at least one channel for scanning, then click **Save and start** after changing settings. **Stop receiver** stops the voice receiver.

## Smart Gain
Smart Gain briefly probes up to twelve selected channels, chooses a supported gain step between 0 and 25.4 dB, then holds that gain fixed while receiving. If the probe cannot run or finds no clear signal, it falls back to 12.5 dB.

Choose **Manual** for your own fixed tuner gain. The input accepts 0–49.6 dB. More gain does not always improve reception; adjust for your antenna and local conditions.

## Squelch
**Automatic (noise tracking)** uses the existing 4 dB SNR setting. **Manual (dBFS)** accepts whole-number thresholds from −100 to −1 dBFS; its default is −47 dBFS.

A higher threshold admits stronger signals only. Too low a threshold can leave the scanner listening to noise instead of moving on. These controls apply to both fixed and scan modes.

## Scan speed
Set **Scan speed** from 100 to 500 ms per channel in 50 ms steps. Lower values scan faster; 200 ms per channel is the default. Begin there and adjust once you have confirmed reception.

## Marine channel workbook
The 0.1.13 voice catalog contains **133 unique analogue receive carriers**, including relevant duplex sides and Dutch supplementary/private channels.

- **Marine channel list** downloads the supplied workbook.
- **Export current** saves your current channel list.
- **Import Excel** reads a compatible workbook, including an SDRCC workbook; Aviation rows are ignored and Marine rows retained.

The supported Marine receive range is 155.775–162.600 MHz. AIS, DSC and other data-only allocations are excluded from Voice. AIS reception remains the job of AIS-catcher.

When older channel banks migrate, the Bridge matches by frequency, keeps scan choices and custom voice channels, and removes obsolete data-only entries.
