# The GUI, Explained Line by Line

This guide walks through the program window from top to bottom and explains every label, box, tick box and button. After reading it you should be able to point at anything on the screen and say what it is and why it is there.

Open the program (`python gui.py`) and keep it next to this file while you read. All examples use the values the window starts with, which are the settings from the organisers' test file. A picture of the window is in `docs/gui-screenshot.png`.

---

## Part 0: Five ideas you need first

**1. Bit and byte.** A bit is a single 0 or 1. A byte is 8 bits, for example `00011000`. Space standards often say **octet** instead of byte; it means exactly the same thing (8 bits).

**2. Three ways to write the same number.** The window accepts all three:

| Way | Example | How to read it |
|---|---|---|
| Decimal (normal) | `234` | everyday numbers |
| Hexadecimal ("hex") | `0xEA` | base 16: digits 0-9 then A=10, B=11, C=12, D=13, E=14, F=15. One hex digit = 4 bits, so two hex digits = one byte |
| Binary | `0b11101010` | base 2: only 0 and 1 |

All three examples above are the same number, 234. `0x` in front means hex, `0b` means binary. Underscores are only for easy reading: `0b10_0001_0011` is the same as `0b1000010011`.

In the output boxes, bytes are shown in hex as pairs like `EB 90`. Each pair is one byte.

**3. Header, data and checksum.** Almost everything in this program is built the same way: a **header** (labels: who is it for, how long is it), then the **data** (the actual content), then often a **CRC** (a checksum to detect damage). Think of a parcel: the address label, the contents, and a seal that shows if someone opened it.

**4. Layers.** Building a command is like putting a letter in an envelope, the envelope in a parcel, and the parcel in a shipping crate. Each layer adds its own wrapping. The window has one numbered box per layer:

```
1. Packet      the command itself, addressed to one program on the satellite
2. Frame       the packet wrapped for the radio link, addressed to one satellite
3. Coding      the frame protected against radio errors (CLTU)
4. Physical    extra "wake-up" bits so the satellite's receiver can lock on
```

**5. What is a CLTU?** "Communications Link Transmission Unit". It is the finished, protected command that the ground station actually transmits. Making it is the goal of the program.

---

## Part 1: The left side, box "1. PUS telecommand (packetization)"

**Telecommand (TC)** = a command sent from the ground to the satellite. **PUS** = Packet Utilization Standard (ECSS-E-ST-70-41C), the European rulebook for how commands are organised. **Packetization** = putting the command into a packet.

### "Input type" drop-down (three choices)

Different people start from different points, so the program accepts three kinds of starting material:

| Choice | What you type in "Data (hex)" | What the program does | When you would use it |
|---|---|---|---|
| **PUS data field (build the packet)** | only the command content, e.g. `01 02 ... 0A` | builds the 6-byte packet header in front and the CRC behind | the normal case, and what the organisers' test uses |
| **Complete Space Packet (hex)** | a whole packet that someone else already built, header and CRC included | uses it exactly as given (no new header or CRC) and continues with the segment and frame | another tool or team already made the packet; you only need the frame and CLTU |
| **Control command (BC frame only)** | a short command for the satellite's radio receiver itself, not for any program on board | puts it straight into a frame, with no packet and no segment header | resetting the satellite's command receiver |

Why the third one exists: the standard has a special kind of frame (**Type-BC**) that carries housekeeping orders for the satellite's command-acceptance machinery, called **COP-1**. There are only two such orders, and the grey hint line at the bottom of the box lists them:

- **Unlock** = `00`: "clear your lockout and start accepting commands again".
- **Set V(R)** = `82 00 nn`: "set the number of the next frame you expect to nn". V(R) is the receiver's frame counter.

To use it: choose "Control command", tick both **Bypass flag** and **Control command flag** in box 2, type `00`, and click Generate. If you type something else, the program still builds it but shows a warning.

### "Data (hex)" text box

The command content, typed as hex bytes. `01 02 03 04 05 06 07 08 09 0A` is 10 bytes, the example from the organisers' file. You may write `01 02 0A`, `01020A` or `0x01, 0x02, 0x0A`; all are accepted.

What it means depends on the input type chosen above (content, whole packet, or control command).

### The packet header fields

The **packet primary header** is always 6 bytes. In the example it is `18 EA FF FF 00 09`. Each field below fills some bits of it:

| Field on screen | Grey hint | Simple meaning | Example value |
|---|---|---|---|
| **Packet version** | 3 bits, 0 in CCSDS | which version of the packet format; it has always been 0 | `0` |
| **Secondary (data) header present** (tick box) | | one bit that says "the data starts with an extra PUS header". Ticking it only sets this bit; it does not add any bytes. To actually add the extra header bytes, use the optional box below | ticked (as in the organisers' file) |
| **APID** | 11 bits, 0-2047 | Application Process ID: which program on the satellite should receive this command, like a room number in a building | `234` |
| **Sequence flags** | 2 bits (11 = whole packet) | is this a complete packet (`11`) or one piece of a bigger one that was cut up? We always send whole packets | `0b11` |
| **Sequence count** | 14 bits | a running number for packets, so the satellite can spot a missing or repeated one | `0x3FFF` (16383, the largest possible) |
| **Packet Error Control (CRC-16)** (tick box) | | adds a 2-byte checksum at the end of the packet | ticked |

There is also a grey line: **"Packet length field = data bytes - 1 (CRC not counted)"**. This is not a setting; it tells you how the program fills in the length part of the header. 10 data bytes gives `00 09` (9). The "minus 1" is a standard trick so that the field can never be wasted on the impossible value "zero bytes". Leaving the CRC out of the count is what the focal person asked for; plain CCSDS 133.0 would count it and give 11.

**Reading the example header bit by bit:**

```
18 EA  = 000 1 1 00011101010   version 0 | type 1 (= telecommand) | secondary header flag 1 | APID 234
FF FF  = 11 11111111111111      sequence flags 11 (whole packet) | sequence count 16383
00 09  = 9                      packet length field (10 data bytes - 1)
```

"Type 1" is fixed by the program: 1 means telecommand, 0 would mean telemetry (data coming down).

### The optional box "build PUS-C secondary header in front of the data"

Off by default (the organisers' test does not use it). If you tick **Add PUS secondary header**, the program builds the extra PUS header bytes and puts them in front of your data. These tell the satellite which kind of command this is:

| Field | Meaning | Default |
|---|---|---|
| **PUS version** | 2 = PUS-C, the current edition (ECSS-E-ST-70-41C) | `2` |
| **Ack flags** | 4 bits: which reports the satellite should send back (accepted, started, progress, completed). `0b0000` = no reports | `0b0000` |
| **Service type** | the family of command. 17 = "test" service | `17` |
| **Message subtype** | the exact command inside that family. Service 17, subtype 1 = "are you alive?" check | `1` |
| **Source ID** | who on the ground sent the command | `0` |
| **Source ID bytes** | how many bytes the source ID takes (0, 1 or 2; each mission decides) | `2` |

With the defaults this adds 5 bytes: `20 11 01 00 00`.

---

## Part 2: Box "2. TC Transfer Frame (transfer layer)"

The **transfer frame** is the envelope for the radio link. Its 5-byte header says which satellite and which channel. In the example it is `22 13 48 19 00`.

| Field | Simple meaning | Example |
|---|---|---|
| **Frame version** (fixed text) | always `00` for telecommand frames (CCSDS 232.0) | `00` |
| **Bypass flag (Type-B)** | **on** = "accept this frame immediately, skip the usual in-order checking" (Type-B, used for urgent or test commands). **off** = Type-A, where the satellite checks frames arrive in order and asks for a resend if one is missing | on (BD frame, as in the test file) |
| **Control command flag (Type-C)** | **on** = the frame carries a control command (Unlock / Set V(R)) instead of a packet. Needs bypass on | off |
| **Spacecraft ID (SCID)** | which satellite, 10 bits (0-1023). Every satellite has its own number so it ignores commands for others | `0b10_0001_0011` = 531 |
| **Virtual channel ID** | the radio link is split into up to 64 logical "lanes"; this picks one | `18` |
| **Frame sequence no.** | the frame's running number, 0-255 | `0` |
| **Frame Error Control Field (CRC-16)** (tick box) | a 2-byte checksum over the whole frame. The standard we were given (ECSS-E-ST-50-04C) makes it compulsory, so the program warns if you untick it | ticked |
| **Segment header** (fixed text) | one byte put in front of the packet. Its first two bits say "whole packet" (`11`), fixed as the focal person asked | `11` |
| **MAP ID** | the last 6 bits of the segment header: a further sub-lane inside the virtual channel | `0b111111` = 63, so the segment header byte is `FF` |
| **Frame length** (calculated, not typed) | total frame size, and the value written in the header, which is size - 1 | `26 octets (field value 25)` |

**The flag combinations, in one table:**

| Bypass | Control | Frame type | Carries |
|---|---|---|---|
| off | off | AD | a packet, with in-order checking |
| on | off | BD | a packet, accepted directly (the test file uses this) |
| on | on | BC | a control command |
| off | on | not allowed | the program shows an error |

**Reading the example frame header bit by bit:**

```
22 = 00 1 0 00 10       version 00 | bypass 1 | control 0 | spare 00 | first 2 bits of SCID
13 = 00010011           last 8 bits of SCID  ->  SCID = 10 0001 0011 = 531
48 = 010010 00          VCID 010010 = 18 | first 2 bits of frame length
19 = 00011001           rest of frame length -> 25 (so the frame is 26 bytes)
00 = 00000000           frame sequence number 0
```

**What the 26 bytes are:** 5 header + 1 segment header (`FF`) + 18 packet + 2 FECF = 26.

---

## Part 3: Box "3. Synchronization and channel coding"

This layer turns the frame into the CLTU. It makes the frame survive a noisy radio link and lets the receiver find where it starts.

| Item | Simple meaning |
|---|---|
| **Randomizer on** (tick box) | Mixes the bits with a fixed pseudo-random pattern so there are no long runs of only 0s or only 1s. Long runs make the receiver lose its timing. The satellite undoes it with the same pattern. Compulsory in ECSS-E-ST-50-04C, so the program warns if you untick it |
| **Coding: BCH(63,56), 7 data bytes + 1 parity byte per codeblock** | The frame is cut into blocks of 7 bytes. Each block gets 1 extra **parity byte** calculated from it. The receiver can then **correct** one wrong bit per block, or detect more. A block of 7 + 1 = 8 bytes is a **codeblock** |
| **Start sequence: EB 90** | A fixed 2-byte pattern that says "a CLTU starts here" |
| **Fill byte: 55** | If the frame doesn't divide evenly into 7-byte blocks, `55` bytes fill up the last block. `55` is `01010101` |
| **Tail sequence: C5 C5 C5 C5 C5 C5 C5 79** | A fixed 8-byte pattern that says "the CLTU ends here". It is designed to fail the parity check on purpose, so the receiver knows the data is over |

The order of steps, for the example:

```
frame 26 bytes  ->  + 2 fill bytes (55 55) = 28 bytes  ->  randomize  ->  cut into 4 blocks of 7
->  add 1 parity byte to each = 4 codeblocks of 8 bytes = 32 bytes
->  EB 90 (2) + 32 + tail (8) = CLTU of 42 bytes
```

---

## Part 4: Box "4. Physical layer (PLOP sequences)"

**PLOP** = Physical Layer Operations Procedure. Before the CLTU, the ground station sends a burst of alternating 0s and 1s so the satellite's receiver can lock on to the signal, like tapping a microphone before speaking.

| Field | Meaning | Default |
|---|---|---|
| **Acquisition sequence** | how many bytes of alternating bits go *before* the CLTU. The standard says at least 128 bits = 16 bytes, so the program warns below 16 | `16` |
| **Idle sequence** | how many bytes of alternating bits go *after* it, to keep the receiver locked. At least 1 byte | `1` |
| **Pattern** | which way the alternating bits start: `0x55` = 0101..., `0xAA` = 1010.... Both are alternating; `0x55` is the default | `0x55` |

Example: 16 + 42 + 1 = 59 bytes. Turning these bits into actual radio waves (modulation) is done by the radio hardware, not by this program.

---

## Part 5: The buttons

| Button | What it does |
|---|---|
| **Generate CLTU** | Reads every field, runs all four layers, fills the output boxes on the right. Runs automatically when the program opens. If a value is wrong (e.g. APID 3000, which doesn't fit in 11 bits), a message explains the problem |
| **Save CLTU (.bin)** | Saves the CLTU as raw bytes, the format a radio or another program would read. The file is exactly 42 bytes for the example |
| **Save CLTU (.hex)** | Saves the CLTU as readable text, `EB 90 DD ...`, which you can open in Notepad |
| **Load reference file & validate** | Opens a test file in the organisers' format (`test_vectors/TC_chain_configurations.txt`). It builds each test case and compares packet, segment, frame and CLTU **byte for byte** with the expected answers, shows PASS or FAIL for each, and then copies the test's settings into the form so the jury can see them |
| **Self-check (decode)** | Does the satellite's job in reverse: finds `EB 90` and the tail, checks every parity byte, un-randomizes, and checks the frame CRC. If everything matches the frame we built, it says **PASSED**. This proves the output is internally consistent, not just "looks right" |
| **Save full report (.txt)** | Saves every intermediate stage, in both hex and binary, to a text file you can print or attach |

---

## Part 6: The right side, outputs

### "Show as: Hexadecimal / Binary"

Switches all output boxes between hex (`EB 90`) and binary (`11101011 10010000`). Same data, different writing. Binary is useful for pointing at individual bits, for example the bypass flag.

### Status line (top right)

Green: `Generated: CLTU of 42 bytes`. It turns **red** and adds a sentence when something breaks a rule of the standard, such as the CRC switched off or a too-short acquisition sequence. The program still builds the output; the red text is a warning, not an error.

### The three layer boxes

These are what the focal person asked for: each layer's output in its own hex field.

| Box | What it shows | Example size |
|---|---|---|
| **Transfer layer output: TC Transfer Frame** | the finished frame | 26 bytes |
| **Synchronization & channel coding layer output: CLTU** | the CLTU: `EB 90`, codeblocks, tail | 42 bytes |
| **Physical layer output: acquisition + CLTU + idle** | 16 bytes of `55`, the CLTU, then 1 byte of `55` | 59 bytes |

### "Every intermediate stage"

The whole chain, step by step. Each entry looks like `[Layer] Name (size) - note`, followed by the bytes. With the example settings you will see:

| Entry | What it is |
|---|---|
| [Packet] Packet primary header (6 bytes) | `18 EA FF FF 00 09`, decoded in Part 1 |
| [Packet] Packet data field (10 bytes) | your data, `01 ... 0A` |
| [Packet] Packet CRC (2 bytes) | `CF F0`, checksum over header + data |
| [Packet] PUS packet (18 bytes) | header + data + CRC together |
| [Transfer] Segment (19 bytes) | `FF` + the packet |
| [Transfer] Frame primary header (5 bytes) | `22 13 48 19 00`, decoded in Part 2 |
| [Transfer] FECF (2 bytes) | `6D 25`, checksum over the whole frame |
| [Transfer] TC Transfer Frame (26 bytes) | the finished frame |
| [Coding] Frame + fill (28 bytes) | the frame plus `55 55` |
| [Coding] Randomized data (28 bytes) | after mixing with the random pattern |
| [Coding] BCH codeblocks (32 bytes) | 4 blocks of 7 bytes + 1 parity byte each |
| [Coding] CLTU (42 bytes) | start + codeblocks + tail |
| [Physical] Physical layer stream (59 bytes) | acquisition + CLTU + idle |

If you turn on the optional PUS header, an extra "[Packet] PUS secondary header" entry appears. With the control-command input, the packet entries are replaced by "[Transfer] Control command".

---

## Part 7: A two-minute demo you can give

1. "This is our CLTU generator. On the left are the inputs for each layer, on the right the output of each layer."
2. Point at box 1: "Here we enter the command data and the packet header fields. APID 234 is the program on board that receives it."
3. Point at box 2: "This is the transfer frame. Bypass on means a Type-BD frame; spacecraft ID 531, virtual channel 18."
4. Point at box 3: "The coding layer randomizes the frame, adds BCH error correction, and puts the start and tail sequences around it."
5. Click **Generate CLTU**, point at the three boxes: "Here is each layer's output: the 26-byte frame, the 42-byte CLTU, and the physical stream."
6. Switch to **Binary** and back.
7. Click **Load reference file & validate**, choose the test file: "Every stage matches the organisers' reference byte for byte."
8. Click **Self-check (decode)**: "And we can take our own CLTU apart again: all BCH blocks pass and the frame CRC is correct."
9. Click **Save CLTU (.bin)**: "This is the file the ground station would transmit."

---

## Part 8: Questions the jury may ask about the screen

**Why does the length field say 9 when there are 12 bytes after the header?**
The field holds "data bytes minus 1" and doesn't count the 2 CRC bytes, as the focal person instructed. Plain CCSDS 133.0 would give 11.

**Why does the frame length say 25 for a 26-byte frame?**
The standard stores "length minus 1".

**What happens if I untick the randomizer?**
The CLTU is built without it, and the status line warns that ECSS-E-ST-50-04C clause 8.4.2 requires it.

**Why is there a fill byte?**
26 bytes don't divide into 7-byte blocks; 28 do, so 2 bytes of `55` are added.

**What does the self-check prove?**
That a receiver following the standard can get our exact frame back out of our CLTU.

**Why three input types?**
Normally you build from command data. The other two cover a packet someone else built, and the special control commands for the satellite's command receiver.

**Can I type a different SCID or data?**
Yes. Change any field and click Generate. Numbers can be decimal, `0x` hex or `0b` binary. The program refuses values that don't fit in their bits and says why.
