# How the CLTU Generator Works, Step by Step

This explains the program from zero. We follow **one real example**, the organisers' own test case, through every step. Every byte you see here is the program's real output, and it matches the organisers' reference exactly.

Read it once slowly with the program open next to you. Click **Generate CLTU** and find each step in the "Every intermediate stage" box as you read.

---

## 0. Three ideas you need before anything else

### Idea 1: Everything is bytes, and we write bytes in hex

A **bit** is a 0 or a 1. A **byte** is 8 bits. Instead of writing `00011000`, we split it into two groups of 4 bits (`0001 1000`) and write one symbol per group: `18`. That is **hexadecimal (hex)**.

| 4 bits | hex | | 4 bits | hex |
|---|---|---|---|---|
| 0000 | 0 | | 1000 | 8 |
| 0001 | 1 | | 1001 | 9 |
| 0010 | 2 | | 1010 | A |
| 0011 | 3 | | 1011 | B |
| 0100 | 4 | | 1100 | C |
| 0101 | 5 | | 1101 | D |
| 0110 | 6 | | 1110 | E |
| 0111 | 7 | | 1111 | F |

The organisers' file writes bytes in decimal (for example `24`). The program shows hex (`18`). They are the same number. You can switch the program's view to binary at any time.

### Idea 2: Headers pack several small numbers into a few bytes

A header is like a form with boxes of fixed width. A 10-bit box holds a number from 0 to 1023, a 6-bit box holds 0 to 63, and so on. We write each number in binary, put the boxes side by side, and then cut the long row of bits into bytes. You will see this done by hand below.

### Idea 3: The whole job is wrapping, layer by layer

```
 Your command data            01 02 03 04 05 06 07 08 09 0A
      |  add packet header + CRC                          (Packetization)
      v
 PUS packet                   18 EA FF FF 00 09 ...data... CF F0
      |  add segment header                               (Segmentation)
      v
 Segment                      FF + packet
      |  add frame header + frame CRC                     (TRANSFER LAYER)
      v
 TC Transfer Frame            22 13 48 19 00 + segment + 6D 25
      |  fill, randomize, BCH, start + tail               (SYNC & CODING LAYER)
      v
 CLTU                         EB 90 + 4 codeblocks + C5 C5 C5 C5 C5 C5 C5 79
      |  add acquisition + idle sequences                 (PHYSICAL LAYER)
      v
 Bit stream to the radio      55 55 ... 55 + CLTU + 55
```

Each layer only adds things around what it receives. It never changes the inside, except for scrambling, which is undone on the satellite.

---

## 1. Packetization: building the PUS telecommand packet

**Code:** `cltu/space_packet.py`, function `build_space_packet`
**Standards:** CCSDS 133.0-B-2 (Space Packet), ECSS-E-ST-70-41C (PUS)

**What it's for:** the satellite has several programs on board (power, camera, radio and so on). The packet header says *which program* the command is for, and gives it a running number.

**Input in our example:** the 10 data bytes `01 02 03 04 05 06 07 08 09 0A`. In a real mission these would start with the PUS secondary header (service type, subtype and so on) followed by the command's parameters. The organisers give them as one block, so the program accepts them as one block. It can also build the PUS-C secondary header for you (the optional box in the GUI).

### The 6-byte packet header, by hand

| Box | Width | Value | Bits |
|---|---|---|---|
| Packet version | 3 bits | 0 | `000` |
| Packet type | 1 bit | 1 = telecommand | `1` |
| Secondary header flag | 1 bit | 1 = PUS header present | `1` |
| APID (which on-board program) | 11 bits | 234 | `000 1110 1010` |
| Sequence flags | 2 bits | 3 = whole packet | `11` |
| Sequence count | 14 bits | 16383 | `11 1111 1111 1111` |
| Packet data length | 16 bits | 9 | `0000 0000 0000 1001` |

Put the boxes side by side and cut into bytes:

```
000 1 1 000   1110 1010   11 111111   11111111   00000000   00001001
  = 18          = EA         = FF        = FF       = 00       = 09
```

Header = **`18 EA FF FF 00 09`**. That matches the organisers' `TC_Packet[0..5]` = 24, 234, 255, 255, 0, 9.

### The packet CRC (Packet Error Control)

**What it's for:** a CRC is a 2-byte "fingerprint" of the data. The satellite recalculates it. If even one bit was damaged on the way, the fingerprint will not match and the packet is thrown away.

**How:** the bytes are fed one bit at a time through a 16-bit register using a fixed formula (polynomial `0x1021`, starting value `FFFF`). What is left in the register at the end is the CRC. Think of it as a very careful version of the check digit on a CNIC or ISBN number.

**Code:** `cltu/crc.py`, function `crc16`. A classic way to prove a CRC is correct is that the CRC of the text `123456789` must be `29B1`. Our test suite checks exactly that.

Our CRC = **`CF F0`**, which matches `TC_Packet[16..17]` = 207, 240.

**Full packet (18 bytes):** `18 EA FF FF 00 09 01 02 03 04 05 06 07 08 09 0A CF F0`

> **About the length field "9":** the CCSDS rule is "number of bytes after the header, minus 1". After the header there are 10 data bytes plus 2 CRC bytes = 12, so the rule gives 11. For this challenge the focal person asked for the CRC to be left out (data field length - 1), which gives 9, and that is what the program does. If a judge asks, explain that you noticed the difference from the CCSDS standard and checked it with the focal person.

---

## 2. Segmentation: the segment header

**Code:** `cltu/transfer_frame.py`, function `build_segment`
**Standard:** CCSDS 232.0-B-4

One byte is put in front of the packet:

| Box | Width | Value |
|---|---|---|
| Sequence flags | 2 bits | `11` = this segment holds a whole packet, not a piece |
| MAP ID | 6 bits | 63 = `111111` (a sub-channel number, set by the mission) |

`11` + `111111` = `1111 1111` = **`FF`**. Segment = `FF` + packet (19 bytes). This matches `TC_Segment`.

The focal person said the segment header should be fixed in the code. The sequence flags are fixed at `11`. The MAP ID is shown in the form because the organisers' configuration file lists it as a mission setting.

---

## 3. Transfer layer: the TC Transfer Frame

**Code:** `cltu/transfer_frame.py`, functions `build_primary_header` and `build_transfer_frame`
**Standard:** CCSDS 232.0-B-4, TC Space Data Link Protocol

**What it's for:** this is the envelope with the address. It says *which spacecraft*, *which virtual channel*, *how long the frame is*, and *which number frame this is*.

### The 5-byte frame header, by hand

| Box | Width | Value | Bits |
|---|---|---|---|
| Version | 2 bits | 0 | `00` |
| Bypass flag | 1 bit | 1 (Type-B: skip the acceptance checks) | `1` |
| Control command flag | 1 bit | 0 (Type-D: carries data) | `0` |
| Spare | 2 bits | 0 | `00` |
| Spacecraft ID (SCID) | 10 bits | 531 | `10 0001 0011` |
| Virtual channel ID (VCID) | 6 bits | 18 | `010010` |
| Frame length | 10 bits | total bytes − 1 = 26 − 1 = 25 | `00 0001 1001` |
| Frame sequence number | 8 bits | 0 | `0000 0000` |

```
00 1 0 00 10   0001 0011   010010 00   0001 1001   0000 0000
  = 22           = 13        = 48        = 19        = 00
```

Header = **`22 13 48 19 00`**. That matches `Transfer_Frame[0..4]` = 34, 19, 72, 25, 0.

**Why 26 bytes?** 5 (header) + 19 (segment) + 2 (frame CRC) = 26. The field stores 25 because CCSDS always stores "length − 1". A frame can be at most 1024 bytes, and the program refuses anything larger.

**Frame types**, which are the two flags together:
- **AD** (bypass 0, control 0): normal data with the full checking procedure (COP-1).
- **BD** (bypass 1, control 0): data that skips the checks. This is our case and is common for CubeSats.
- **BC** (bypass 1, control 1): a control command to the satellite's frame-receiving logic, for example "Unlock". It carries no packet and no segment header.
- Bypass 0 with control 1 is **not allowed**. The program shows an error if you try it, and the organisers' file also calls it "illegal".

### The frame CRC (FECF, Frame Error Control Field)

This is the same CRC as before, now computed over the whole frame (header + segment), and added at the end: **`6D 25`**. That matches `Transfer_Frame[24..25]` = 109, 37.

**Transfer layer output (26 bytes):**
`22 13 48 19 00 FF 18 EA FF FF 00 09 01 02 03 04 05 06 07 08 09 0A CF F0 6D 25`

---

## 4. Synchronization and channel coding layer: making the CLTU

**Code:** `cltu/sync_coding.py` (`build_cltu`), `cltu/randomizer.py`, `cltu/bch.py`
**Standard:** CCSDS 231.0-B-4, TC Synchronization and Channel Coding

This layer prepares the frame to survive a noisy radio trip. It has four small steps.

### Step 4a: Fill, to make the length a multiple of 7

BCH works on blocks of exactly 7 bytes. Our frame is 26 bytes, and the next multiple of 7 is 28, so we add **2 fill bytes of `55`** (`01010101`, alternating bits).

### Step 4b: Randomize (scramble)

**What it's for:** a radio receiver keeps time by watching the signal flip between 0 and 1. A long run of identical bits (such as the `FF FF` in our header) gives it nothing to lock on to. So we mix the data with a fixed, random-looking pattern to make sure there are plenty of flips.

**How:** a tiny 8-bit circuit (a shift register) generates the pattern. It starts as all ones and follows the formula given in the standard. Its first bytes are always:

```
FF 39 9E 5A 68 E9 06 F5 6C 89 2F A1 31 5E 08 C0 52 A8 BB AE 4E C2 C7 ED 66 DC 38 D4
```

The standard itself prints the first 40 bits (`FF 39 9E 5A 68`), and our test suite checks them.

Each data byte is combined with the pattern byte using **XOR** (same bits give 0, different bits give 1):

```
data     22 13 48 19 00 FF 18 ...
pattern  FF 39 9E 5A 68 E9 06 ...
XOR      DD 2A D6 43 68 16 1E ...
```

**Why the satellite can undo it:** XOR with the same pattern twice gives back the original. The satellite generates the same pattern and XORs again.

> **Order:** the organisers' file says *"Filler Bits are added and then whole frame is randomized"*, so the program fills first and then randomizes, which matches their reference exactly. The standard the focal person gave you (ECSS-E-ST-50-04C, clause 8.4.4) allows this: *"The randomization can also be applied to the fill bits"*. The receiver throws the fill away using the frame length.

### Step 4c: BCH coding (error correction)

**What it's for:** the CRC can only *detect* damage. BCH can *repair* it. It adds a little extra information so the satellite can fix a single flipped bit in a block, or detect up to three.

**How:**
1. Cut the 28 scrambled bytes into 4 blocks of 7 bytes.
2. For each block, compute 7 check bits. This is a division of the 56 data bits by a fixed polynomial, g(x) = x⁷ + x⁶ + x² + 1, keeping the remainder, just like long division leaves a remainder.
3. Flip (complement) those 7 bits, and add one more `0` bit (the "filler bit") to make a full byte.
4. Each block becomes **7 data bytes + 1 check byte = 8 bytes**, called a *codeblock*.

| Block | 7 data bytes | Check byte |
|---|---|---|
| 1 | DD 2A D6 43 68 16 1E | **66** |
| 2 | 1F 93 76 2F A8 30 5C | **A4** |
| 3 | 0B C4 57 AE BC A6 47 | **5A** |
| 4 | C8 08 1D 0B F9 6D 81 | **54** |

**Code:** `cltu/bch.py`, function `parity_bits`. It is a 7-bit shift register, which is exactly how the hardware does the division. Our tests prove the maths three ways: each codeword divides exactly by g(x), every possible single-bit error is detected, and the four codeblocks above match the organisers' CLTU.

### Step 4d: Start and tail sequences

- **Start sequence `EB 90`** goes in front. It's a special 16-bit pattern the satellite is always listening for. When it sees it, it knows "a command begins here".
- **Tail sequence `C5 C5 C5 C5 C5 C5 C5 79`** goes at the end. It is designed so that it fails the BCH check. When the satellite's decoder hits it, it knows "the command has ended".

**CLTU, the coding layer output (42 bytes = 2 + 4×8 + 8):**

```
EB 90
DD 2A D6 43 68 16 1E 66
1F 93 76 2F A8 30 5C A4
0B C4 57 AE BC A6 47 5A
C8 08 1D 0B F9 6D 81 54
C5 C5 C5 C5 C5 C5 C5 79
```

This matches the organisers' `CLTU[0..41]` byte for byte.

---

## 5. Physical layer: helping the radio lock on

**Code:** `cltu/physical.py`
**Standard:** CCSDS 231.0-B-4, Physical Layer Operations Procedure (PLOP)

Before the CLTU, the ground station sends an **acquisition sequence**: alternating 1s and 0s (`55 55 55 ...`). It's like humming a note before singing, so the satellite's radio can tune in to the timing. ECSS-E-ST-50-04C (clause 9.2.1) requires at least 128 bits, which is 16 bytes.

After the CLTU comes an **idle sequence** (also alternating bits, at least 8 bits). It keeps the radio locked until the next command.

- **PLOP-1:** the radio carrier is switched off after each CLTU.
- **PLOP-2:** the carrier stays on and idle sequences fill the gaps.

**Physical layer output:** `55` × 16 + CLTU + `55`. Both lengths and the pattern (`55` or `AA`) can be set in the GUI.

The organisers gave no reference for this layer. We followed the standard and made the lengths configurable. Turning these bits into an actual radio wave (modulation) is done by radio hardware, outside this software.

---

## 6. How we know it's right

1. **Organisers' reference:** packet, segment, frame and CLTU all match byte for byte (`python validate.py`, or the GUI button).
2. **37 automated tests** (`python -m unittest discover -s tests -v`). They include known published values (CRC `29B1`, randomizer `FF 39 9E 5A 68`), mathematical checks of BCH, hand-worked headers, limits (1024-byte frames, illegal flag combinations), a full round trip, and 300 random commands and settings that all decode back correctly.
3. **Self-check (decode):** the program takes its own CLTU apart again. It finds the start and tail, checks every BCH codeblock, de-randomizes, and checks the frame CRC. If we damage one byte, the check fails, as it should.

---

## 7. One-paragraph summary to memorise

> Our software takes the command data and wraps it in a CCSDS Space Packet with a PUS header and a CRC. It adds a one-byte segment header and wraps that in a TC Transfer Frame whose header carries the spacecraft ID, virtual channel, frame length and sequence number, followed by a frame CRC. It pads the frame to a multiple of 7 bytes, scrambles it with the CCSDS pseudo-random sequence, and protects each 7-byte block with a BCH(63,56) check byte. It frames the result with the EB90 start sequence and the C5…79 tail sequence to form the CLTU. Finally it adds acquisition and idle sequences for the physical layer. Each layer's output is shown in hex and binary, and the result matches the organisers' reference vectors byte for byte.
