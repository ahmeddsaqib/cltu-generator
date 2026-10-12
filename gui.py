"""Graphical user interface for the CCSDS TC CLTU generator.

Run with:   python gui.py
Needs only Python 3 (Tkinter is included with the standard Windows/macOS installers).
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from cltu import formatting
from cltu.decoder import decode_cltu
from cltu.physical import ALTERNATING_01, ALTERNATING_10, PhysicalConfig
from cltu.pipeline import (GeneratorConfig, INPUT_CONTROL_COMMAND, INPUT_PUS_DATA,
                           INPUT_RAW_PACKET, run)
from cltu.space_packet import PusSecondaryHeader, SpacePacketConfig
from cltu.sync_coding import CodingConfig, START_SEQUENCE, TAIL_SEQUENCE
from cltu.transfer_frame import TransferFrameConfig
import validate

APP_TITLE = "CCSDS TC CLTU Generator"
HERE = os.path.dirname(os.path.abspath(__file__))

INPUT_MODES = {
    "PUS data field (build the packet)": INPUT_PUS_DATA,
    "Complete Space Packet (hex)": INPUT_RAW_PACKET,
    "Control command (BC frame only)": INPUT_CONTROL_COMMAND,
}
PATTERNS = {"0x55 (0101...)": ALTERNATING_01, "0xAA (1010...)": ALTERNATING_10}
FRAME_TYPE_BY_FLAGS = {(0, 0): "AD", (1, 0): "BD", (1, 1): "BC"}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1350x860")
        self.minsize(1100, 700)
        self.result = None
        self.vars = {}
        self._build_layout()
        self.generate()

    # ------------------------------------------------------------------ layout
    def _build_layout(self):
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        left = self._scrollable(paned)
        right = ttk.Frame(paned, padding=6)
        paned.add(left.master_frame, weight=0)
        paned.add(right, weight=1)

        self._packet_inputs(left)
        self._frame_inputs(left)
        self._coding_inputs(left)
        self._physical_inputs(left)
        self._buttons(left)
        self._outputs(right)

    def _scrollable(self, parent):
        outer = ttk.Frame(parent)
        canvas = tk.Canvas(outer, width=560, highlightthickness=0)
        bar = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
        inner = ttk.Frame(canvas, padding=6)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=bar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        bar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))
        inner.master_frame = outer
        return inner

    def _entry(self, parent, row, label, key, default, width=16, tip=""):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=1)
        var = tk.StringVar(value=default)
        ttk.Entry(parent, textvariable=var, width=width).grid(row=row, column=1, sticky="w")
        if tip:
            ttk.Label(parent, text=tip, foreground="#666").grid(row=row, column=2, sticky="w", padx=4)
        self.vars[key] = var

    def _check(self, parent, row, label, key, default, tip=""):
        var = tk.BooleanVar(value=default)
        ttk.Checkbutton(parent, text=label, variable=var).grid(row=row, column=0, columnspan=2,
                                                               sticky="w", pady=1)
        if tip:
            ttk.Label(parent, text=tip, foreground="#666").grid(row=row, column=2, sticky="w", padx=4)
        self.vars[key] = var

    def _combo(self, parent, row, label, key, options, width=40):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=1)
        var = tk.StringVar(value=options[0])
        ttk.Combobox(parent, textvariable=var, values=options, state="readonly",
                     width=width).grid(row=row, column=1, columnspan=2, sticky="w")
        self.vars[key] = var

    def _packet_inputs(self, parent):
        box = ttk.LabelFrame(parent, text="1. PUS telecommand (packetization)", padding=6)
        box.pack(fill=tk.X, pady=4)
        self._combo(box, 0, "Input type", "input_mode", list(INPUT_MODES), width=34)
        ttk.Label(box, text="Data (hex)").grid(row=1, column=0, sticky="nw")
        self.data_text = tk.Text(box, height=4, width=40, font=("Consolas", 10))
        self.data_text.grid(row=1, column=1, columnspan=2, sticky="w", pady=2)
        self.data_text.insert("1.0", "01 02 03 04 05 06 07 08 09 0A")
        ttk.Label(box, text="Control commands: Unlock = 00, Set V(R) = 82 00 nn",
                  foreground="#666").grid(row=10, column=0, columnspan=3, sticky="w")
        self._entry(box, 2, "Packet version", "pkt_version", "0", tip="3 bits, 0 in CCSDS")
        self._check(box, 3, "Secondary (data) header present", "sec_flag", True)
        self._entry(box, 4, "APID", "apid", "234", tip="11 bits, 0-2047")
        self._entry(box, 5, "Sequence flags", "seq_flags", "0b11", tip="2 bits (11 = whole packet)")
        self._entry(box, 6, "Sequence count", "seq_count", "0x3FFF", tip="14 bits")
        self._check(box, 7, "Packet Error Control (CRC-16)", "pkt_crc", True)
        ttk.Label(box, text="Packet length field = data bytes - 1 (CRC not counted)",
                  foreground="#666").grid(row=8, column=0, columnspan=3, sticky="w")

        pus = ttk.LabelFrame(box, text="Optional: build PUS-C secondary header in front of the data",
                             padding=4)
        pus.grid(row=9, column=0, columnspan=3, sticky="we", pady=4)
        self._check(pus, 0, "Add PUS secondary header", "pus_on", False)
        self._entry(pus, 1, "PUS version", "pus_version", "2", width=6, tip="2 = PUS-C")
        self._entry(pus, 2, "Ack flags", "pus_ack", "0b0000", width=6, tip="4 bits")
        self._entry(pus, 3, "Service type", "pus_service", "17", width=6)
        self._entry(pus, 4, "Message subtype", "pus_subtype", "1", width=6)
        self._entry(pus, 5, "Source ID", "pus_source", "0", width=6)
        self._entry(pus, 6, "Source ID bytes", "pus_source_bytes", "2", width=6, tip="0, 1 or 2")

    def _frame_inputs(self, parent):
        box = ttk.LabelFrame(parent, text="2. TC Transfer Frame (transfer layer)", padding=6)
        box.pack(fill=tk.X, pady=4)
        ttk.Label(box, text="Frame version").grid(row=0, column=0, sticky="w")
        ttk.Label(box, text="00 (fixed by CCSDS 232.0)").grid(row=0, column=1, columnspan=2, sticky="w")
        self._check(box, 1, "Bypass flag (Type-B)", "bypass", True, tip="off = Type-A (AD)")
        self._check(box, 2, "Control command flag (Type-C)", "control", False, tip="needs bypass on")
        self._entry(box, 3, "Spacecraft ID (SCID)", "scid", "0b10_0001_0011", tip="10 bits, 0-1023")
        self._entry(box, 4, "Virtual channel ID", "vcid", "18", tip="6 bits, 0-63")
        self._entry(box, 5, "Frame sequence no.", "frame_seq", "0", tip="8 bits, 0-255")
        self._check(box, 6, "Frame Error Control Field (CRC-16)", "fecf", True)
        ttk.Label(box, text="Segment header").grid(row=7, column=0, sticky="w")
        ttk.Label(box, text="sequence flags 11 (fixed)").grid(row=7, column=1, columnspan=2, sticky="w")
        self._entry(box, 8, "MAP ID", "map_id", "0b111111", tip="6 bits, 0-63")
        ttk.Label(box, text="Frame length").grid(row=9, column=0, sticky="w")
        self.frame_length_label = ttk.Label(box, text="(calculated)")
        self.frame_length_label.grid(row=9, column=1, columnspan=2, sticky="w")

    def _coding_inputs(self, parent):
        box = ttk.LabelFrame(parent, text="3. Synchronization and channel coding", padding=6)
        box.pack(fill=tk.X, pady=4)
        self._check(box, 0, "Randomizer on", "randomizer", True)
        info = ("Coding: BCH(63,56), 7 data bytes + 1 parity byte per codeblock\n"
                "Start sequence: %s     Fill byte: 55\nTail sequence: %s"
                % (formatting.to_hex(START_SEQUENCE), formatting.to_hex(TAIL_SEQUENCE)))
        ttk.Label(box, text=info, foreground="#444").grid(row=1, column=0, columnspan=3, sticky="w")

    def _physical_inputs(self, parent):
        box = ttk.LabelFrame(parent, text="4. Physical layer (PLOP sequences)", padding=6)
        box.pack(fill=tk.X, pady=4)
        self._entry(box, 0, "Acquisition sequence", "acq", "16", width=6, tip="octets (16 or more)")
        self._entry(box, 1, "Idle sequence", "idle", "1", width=6, tip="octets (1 or more)")
        self._combo(box, 2, "Pattern", "pattern", list(PATTERNS), width=16)

    def _buttons(self, parent):
        box = ttk.Frame(parent, padding=4)
        box.pack(fill=tk.X, pady=6)
        ttk.Button(box, text="Generate CLTU", command=self.generate).grid(row=0, column=0, sticky="we", padx=2, pady=2)
        ttk.Button(box, text="Save CLTU (.bin)", command=self.save_bin).grid(row=0, column=1, sticky="we", padx=2, pady=2)
        ttk.Button(box, text="Save CLTU (.hex)", command=self.save_hex).grid(row=0, column=2, sticky="we", padx=2, pady=2)
        ttk.Button(box, text="Load reference file & validate", command=self.validate_file).grid(
            row=1, column=0, columnspan=2, sticky="we", padx=2, pady=2)
        ttk.Button(box, text="Self-check (decode)", command=self.self_check).grid(row=1, column=2, sticky="we", padx=2, pady=2)
        ttk.Button(box, text="Save full report (.txt)", command=self.save_report).grid(
            row=2, column=0, columnspan=3, sticky="we", padx=2, pady=2)

    def _outputs(self, parent):
        top = ttk.Frame(parent)
        top.pack(fill=tk.X)
        ttk.Label(top, text="Show as:").pack(side=tk.LEFT)
        self.vars["view"] = tk.StringVar(value="hex")
        for text, value in (("Hexadecimal", "hex"), ("Binary", "bin")):
            ttk.Radiobutton(top, text=text, value=value, variable=self.vars["view"],
                            command=self.refresh_outputs).pack(side=tk.LEFT, padx=4)
        self.status = ttk.Label(top, text="", foreground="#05612b")
        self.status.pack(side=tk.RIGHT)

        self.layer_boxes = {}
        for key, title in (("Transfer", "Transfer layer output: TC Transfer Frame"),
                           ("Coding", "Synchronization & channel coding layer output: CLTU"),
                           ("Physical", "Physical layer output: acquisition + CLTU + idle")):
            frame = ttk.LabelFrame(parent, text=title, padding=4)
            frame.pack(fill=tk.X, pady=3)
            text = tk.Text(frame, height=5, wrap=tk.WORD, font=("Consolas", 10))
            text.pack(fill=tk.X)
            self.layer_boxes[key] = text

        frame = ttk.LabelFrame(parent, text="Every intermediate stage", padding=4)
        frame.pack(fill=tk.BOTH, expand=True, pady=3)
        self.details = tk.Text(frame, wrap=tk.WORD, font=("Consolas", 10))
        bar = ttk.Scrollbar(frame, command=self.details.yview)
        self.details.configure(yscrollcommand=bar.set)
        self.details.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        bar.pack(side=tk.RIGHT, fill=tk.Y)

    # ------------------------------------------------------------- read inputs
    def _int(self, key, name):
        try:
            return formatting.parse_int(self.vars[key].get())
        except ValueError:
            raise ValueError("%s: '%s' is not a valid number" % (name, self.vars[key].get()))

    def read_config(self) -> GeneratorConfig:
        bypass = int(self.vars["bypass"].get())
        control = int(self.vars["control"].get())
        if (bypass, control) not in FRAME_TYPE_BY_FLAGS:
            raise ValueError("Bypass off + control command on is not allowed by CCSDS 232.0 "
                             "(there is no Type-AC frame).")
        secondary = None
        if self.vars["pus_on"].get():
            secondary = PusSecondaryHeader(
                pus_version=self._int("pus_version", "PUS version"),
                ack_flags=self._int("pus_ack", "Ack flags"),
                service_type=self._int("pus_service", "Service type"),
                service_subtype=self._int("pus_subtype", "Message subtype"),
                source_id=self._int("pus_source", "Source ID"),
                source_id_bytes=self._int("pus_source_bytes", "Source ID bytes"))
        return GeneratorConfig(
            input_mode=INPUT_MODES[self.vars["input_mode"].get()],
            user_data=formatting.parse_hex(self.data_text.get("1.0", tk.END)),
            secondary_header=secondary,
            packet=SpacePacketConfig(
                apid=self._int("apid", "APID"),
                version=self._int("pkt_version", "Packet version"),
                secondary_header_flag=int(self.vars["sec_flag"].get()),
                sequence_flags=self._int("seq_flags", "Sequence flags"),
                sequence_count=self._int("seq_count", "Sequence count"),
                error_control=self.vars["pkt_crc"].get()),
            frame=TransferFrameConfig(
                spacecraft_id=self._int("scid", "Spacecraft ID"),
                virtual_channel_id=self._int("vcid", "Virtual channel ID"),
                frame_sequence_number=self._int("frame_seq", "Frame sequence number"),
                frame_type=FRAME_TYPE_BY_FLAGS[(bypass, control)],
                map_id=self._int("map_id", "MAP ID"),
                use_fecf=self.vars["fecf"].get()),
            coding=CodingConfig(randomizer=self.vars["randomizer"].get()),
            physical=PhysicalConfig(acquisition_octets=self._int("acq", "Acquisition sequence"),
                                    idle_octets=self._int("idle", "Idle sequence"),
                                    pattern=PATTERNS[self.vars["pattern"].get()]))

    # ----------------------------------------------------------------- actions
    def generate(self):
        try:
            self.result = run(self.read_config())
        except ValueError as error:
            self.result = None
            self._set_status("Error: %s" % error, ok=False)
            messagebox.showerror(APP_TITLE, str(error))
            return
        length = len(self.result.frame)
        self.frame_length_label.config(text="%d octets (field value %d)" % (length, length - 1))
        message = "Generated: CLTU of %d bytes" % len(self.result.cltu)
        if self.result.warnings:
            message += "  |  " + " ".join(self.result.warnings)
        self._set_status(message, ok=not self.result.warnings)
        self.refresh_outputs()

    def _fmt(self, data):
        if self.vars["view"].get() == "bin":
            return formatting.to_binary(data)
        return formatting.to_hex(data)

    def refresh_outputs(self):
        if not self.result:
            return
        layer_data = {"Transfer": self.result.frame, "Coding": self.result.cltu,
                      "Physical": self.result.physical}
        for key, box in self.layer_boxes.items():
            box.delete("1.0", tk.END)
            box.insert("1.0", self._fmt(layer_data[key]))
        self.details.delete("1.0", tk.END)
        self.details.insert("1.0", self.report_text())

    def report_text(self):
        lines = []
        for stage in self.result.stages:
            title = "[%s] %s  (%d bytes)" % (stage.layer, stage.name, len(stage.data))
            if stage.note:
                title += "  - " + stage.note
            lines.append(title)
            lines.append(self._fmt(stage.data))
            lines.append("")
        return "\n".join(lines)

    def _set_status(self, text, ok=True):
        self.status.config(text=text, foreground="#05612b" if ok else "#b00020")

    def _ask_save(self, ext, kind):
        if not self.result:
            messagebox.showwarning(APP_TITLE, "Generate a CLTU first.")
            return None
        return filedialog.asksaveasfilename(defaultextension=ext, initialfile="cltu" + ext,
                                            filetypes=[(kind, "*" + ext), ("All files", "*.*")])

    def save_bin(self):
        path = self._ask_save(".bin", "Binary file")
        if path:
            with open(path, "wb") as handle:
                handle.write(self.result.cltu)
            self._set_status("Saved %d bytes to %s" % (len(self.result.cltu), path))

    def save_hex(self):
        path = self._ask_save(".hex", "Hex text file")
        if path:
            with open(path, "w") as handle:
                handle.write(formatting.to_hex(self.result.cltu) + "\n")
            self._set_status("Saved hex to %s" % path)

    def save_report(self):
        path = self._ask_save(".txt", "Text report")
        if path:
            view = self.vars["view"].get()
            parts = []
            for mode in ("hex", "bin"):
                self.vars["view"].set(mode)
                parts.append(("HEXADECIMAL" if mode == "hex" else "BINARY") + "\n\n" + self.report_text())
            self.vars["view"].set(view)
            with open(path, "w") as handle:
                handle.write(APP_TITLE + " - processing report\n\n" + "\n\n".join(parts))
            self._set_status("Saved report to %s" % path)

    def self_check(self):
        if not self.result:
            return
        cfg = self.read_config()
        report = decode_cltu(self.result.cltu, randomizer=cfg.coding.randomizer,
                             has_fecf=cfg.frame.use_fecf)
        same = report.frame == self.result.frame
        lines = ["Start and tail sequences found.",
                 "%d of %d BCH codeblocks pass the parity check."
                 % (sum(report.codeblocks_ok), len(report.codeblocks_ok)),
                 "De-randomized frame equals the generated frame: %s" % ("yes" if same else "NO"),
                 "Frame CRC (FECF) correct: %s" % ("yes" if report.fecf_ok else "NO")]
        if report.ok and same:
            messagebox.showinfo(APP_TITLE, "Self-check PASSED\n\n" + "\n".join(lines))
        else:
            messagebox.showerror(APP_TITLE, "Self-check FAILED\n\n" + "\n".join(lines + report.messages))

    def validate_file(self):
        path = filedialog.askopenfilename(initialdir=os.path.join(HERE, "test_vectors"),
                                          filetypes=[("Reference files", "*.txt"), ("All files", "*.*")])
        if not path:
            return
        try:
            cases = validate.parse_file(path)
        except (OSError, ValueError) as error:
            messagebox.showerror(APP_TITLE, "Could not read the file:\n%s" % error)
            return
        if not cases:
            messagebox.showerror(APP_TITLE, "No test cases found in this file.")
            return
        summary = []
        all_ok = True
        for case in cases:
            cfg = validate.config_from_params(case["params"], case["data"])
            result = run(cfg)
            produced = {"TC_Packet": result.packet, "TC_Segment": result.stage("Segment").data,
                        "Transfer_Frame": result.frame, "CLTU": result.cltu}
            summary.append(case["name"])
            for key in validate.STAGE_KEYS:
                expected = case["expected"][key]
                if not expected:
                    continue
                ok = expected == produced[key]
                all_ok &= ok
                summary.append("   %-15s %s" % (key, "PASS" if ok else
                                                   "FAIL - " + validate.first_difference(expected, produced[key])))
        self._load_case_into_form(cases[0])
        self.generate()
        text = "\n".join(summary)
        if all_ok:
            messagebox.showinfo(APP_TITLE, "All reference stages match.\n\n" + text)
        else:
            messagebox.showerror(APP_TITLE, "Some stages do not match.\n\n" + text)

    def _load_case_into_form(self, case):
        """Show the first test case's settings in the form so the jury can see them."""
        cfg = validate.config_from_params(case["params"], case["data"])
        self.vars["input_mode"].set(list(INPUT_MODES)[0])
        self.data_text.delete("1.0", tk.END)
        self.data_text.insert("1.0", formatting.to_hex(cfg.user_data))
        self.vars["pus_on"].set(False)
        self.vars["pkt_version"].set(str(cfg.packet.version))
        self.vars["sec_flag"].set(bool(cfg.packet.secondary_header_flag))
        self.vars["apid"].set(str(cfg.packet.apid))
        self.vars["seq_flags"].set("0b{:02b}".format(cfg.packet.sequence_flags))
        self.vars["seq_count"].set("0x{:04X}".format(cfg.packet.sequence_count))
        self.vars["pkt_crc"].set(cfg.packet.error_control)
        bypass, control = {"AD": (0, 0), "BD": (1, 0), "BC": (1, 1)}[cfg.frame.frame_type]
        self.vars["bypass"].set(bool(bypass))
        self.vars["control"].set(bool(control))
        self.vars["scid"].set(str(cfg.frame.spacecraft_id))
        self.vars["vcid"].set(str(cfg.frame.virtual_channel_id))
        self.vars["frame_seq"].set(str(cfg.frame.frame_sequence_number))
        self.vars["map_id"].set(str(cfg.frame.map_id))
        self.vars["fecf"].set(True)
        self.vars["randomizer"].set(True)


if __name__ == "__main__":
    App().mainloop()
