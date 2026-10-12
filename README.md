# CCSDS TC CLTU Generator

A standalone program that turns a PUS telecommand into a CCSDS CLTU, ready to send to a CubeSat. It shows the output of every layer in hexadecimal and binary, saves the CLTU as `.bin` and `.hex`, and checks itself against the organisers' reference vectors.

It uses **only Python 3 and its standard library** (Tkinter for the window, unittest for tests). It needs no internet and no extra installs.

## Quick start

1. Install Python 3.8 or newer from python.org. On Windows, tick "Add Python to PATH" during installation. Tkinter comes with it.
2. Copy the whole `cltu-generator` folder to the laptop.
3. Open a terminal (Command Prompt) in that folder and run:

```
python gui.py                              # the graphical program
python validate.py                         # compare with the organisers' reference vectors
python -m unittest discover -s tests -v    # run all 37 automated tests
```

On Linux, if `import tkinter` fails, install it with `sudo apt install python3-tk`.

## What is in the folder

| File | What it does | Standard |
|---|---|---|
| `cltu/space_packet.py` | Builds the PUS telecommand packet (6-byte header, data, CRC) | CCSDS 133.0-B-2, ECSS-E-ST-70-41C |
| `cltu/transfer_frame.py` | Segment header and TC Transfer Frame (5-byte header, FECF) | CCSDS 232.0-B-4, ECSS-E-ST-50-04C |
| `cltu/crc.py` | CRC-16 used for both the packet and the frame | CCSDS 232.0-B-4 |
| `cltu/randomizer.py` | Pseudo-randomizer | CCSDS 231.0-B-4 |
| `cltu/bch.py` | BCH(63,56) encoder | CCSDS 231.0-B-4 |
| `cltu/sync_coding.py` | Fill, randomize, BCH, start and tail sequences, giving the CLTU | CCSDS 231.0-B-4, ECSS-E-ST-50-04C |
| `cltu/physical.py` | Acquisition and idle sequences around the CLTU (PLOP) | CCSDS 231.0-B-4, ECSS-E-ST-50-04C |
| `cltu/pipeline.py` | Runs the whole chain and records every stage | |
| `cltu/decoder.py` | Takes a CLTU apart again to prove it is self-consistent | |
| `gui.py` | The user interface | |
| `validate.py` | Reads the organisers' reference file and compares every stage | |
| `tests/test_chain.py` | 37 automated tests | |
| `test_vectors/` | The organisers' reference file | |
| `docs/` | GUI guide (every field and button explained), explanations, compliance matrix, test report, viva questions | |

## Using the program

1. **Left side:** enter the command data in hex and the packet and frame settings. Every field shows its allowed range.
2. Click **Generate CLTU**.
3. **Right side:** three boxes show the output of the transfer layer, the coding layer and the physical layer. The large box below lists every intermediate stage. Switch between **Hexadecimal** and **Binary** at the top.
4. **Save CLTU (.bin / .hex)** writes the final CLTU to a file.
5. **Load reference file & validate** opens the organisers' file, compares every stage and loads its settings into the form.
6. **Self-check (decode)** takes the CLTU apart again and confirms the BCH codes, the de-randomized frame and the CRC.

## The packet length field

The packet length field is the number of data bytes minus 1. The 2-byte CRC is not counted, as the hackathon focal person instructed, so the reference packet (10 data bytes) gets 9. Plain CCSDS 133.0 would count the CRC and give 11; see `docs/COMPLIANCE.md`, note 1.

The fill bytes are added first and then randomized together with the frame, as the organisers' configuration states. ECSS-E-ST-50-04C clause 8.4.4 allows this.
