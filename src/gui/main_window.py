"""Main application window: glass UI, login, brand/model ops, firmware select,
device info, live display."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFrame,
    QGraphicsDropShadowEffect, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QSlider,
    QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from src.auth.license_client import LicenseClient
from src.core import devices
from src.core.safety import is_protected
from src.core.scatter.scatter_parser import ScatterParser
from src.gui.assets import MARK_SVG, app_icon, svg_pixmap
from src.gui.theme import QSS, apply_acrylic
from src.gui.worker import DeviceInfoWorker, FirmwareLoadWorker, OperationWorker

SENSITIVE = {"FRP_RESET", "NETWORK_UNLOCK", "IMEI_REPAIR", "BOOTLOADER_UNLOCK", "BACKUP_SECURITY"}
SERVER_DEFAULT = "https://epu-api-production.up.railway.app"


class ConsentDialog(QDialog):
    """Shown BEFORE any sensitive operation. Collects IMEI/serial + consent."""
    def __init__(self, parent, operation_label):
        super().__init__(parent)
        self.setWindowTitle("Confirm Sensitive Operation")
        self.setStyleSheet(QSS)
        self.setModal(True)
        lay = QVBoxLayout(self)
        warn = QLabel(
            f"⚠  You are about to perform: <b>{operation_label}</b>.<br><br>"
            "This changes device identity / removes protections. Only proceed if you "
            "are authorized to service this device. This action is recorded with your "
            "username, PC ID and IP, and the device IMEI/serial, for traceability."
        )
        warn.setWordWrap(True)
        lay.addWidget(warn)
        self.imei = QLineEdit(); self.imei.setPlaceholderText("Device IMEI (15 digits)")
        self.serial = QLineEdit(); self.serial.setPlaceholderText("or Serial Number")
        lay.addWidget(QLabel("IMEI")); lay.addWidget(self.imei)
        lay.addWidget(QLabel("Serial")); lay.addWidget(self.serial)
        self.agree = QCheckBox("I confirm I am authorized to service this device.")
        lay.addWidget(self.agree)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._ok); bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.setMinimumWidth(420)

    def _ok(self):
        if not self.agree.isChecked():
            return
        if not (self.imei.text().strip() or self.serial.text().strip()):
            return
        self.accept()

    def values(self):
        return self.imei.text().strip(), self.serial.text().strip(), self.agree.isChecked()


class MainWindow(QWidget):
    COLS = ["", "Partition", "File", "Size", "State"]

    def __init__(self, server_url: str = SERVER_DEFAULT):
        super().__init__()
        self.setObjectName("Root")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(1080, 700)
        self._drag = None
        self.worker: OperationWorker | None = None
        self.info_worker: DeviceInfoWorker | None = None
        self.fw_worker: FirmwareLoadWorker | None = None
        self.scatter_partitions = []
        self.firmware_dir = ""      # where partition images live (for flash)
        self.device_info: dict = {}

        self.lic = LicenseClient(server_url=server_url)
        self.setWindowIcon(app_icon())

        root = QVBoxLayout(self); root.setContentsMargins(16, 16, 16, 16)
        self.glass = QFrame(); self.glass.setObjectName("Glass")
        shadow = QGraphicsDropShadowEffect(blurRadius=40, xOffset=0, yOffset=10)
        shadow.setColor(QColor(0, 0, 0, 160)); self.glass.setGraphicsEffect(shadow)
        root.addWidget(self.glass)
        outer = QVBoxLayout(self.glass); outer.setContentsMargins(0, 0, 0, 0)

        outer.addWidget(self._title_bar())
        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)
        self.stack.addWidget(self._login_page())
        self.stack.addWidget(self._dashboard_page())
        self.setStyleSheet(QSS)

    # ----------------------------- chrome ----------------------------- #
    def _title_bar(self) -> QWidget:
        bar = QWidget(); bar.setObjectName("TitleBar"); bar.setFixedHeight(46)
        h = QHBoxLayout(bar); h.setContentsMargins(14, 0, 12, 0); h.setSpacing(10)
        mark = QLabel(); mark.setPixmap(svg_pixmap(MARK_SVG, 24)); h.addWidget(mark)
        t = QLabel("EASY PHONE UNLOCK  •  MTK Universal Tool"); t.setObjectName("TitleLabel")
        h.addWidget(t); h.addStretch(1)
        mini = QPushButton("–"); mini.setObjectName("Chip"); mini.setFixedWidth(40)
        mini.clicked.connect(self.showMinimized)
        close = QPushButton("✕"); close.setObjectName("Chip"); close.setFixedWidth(40)
        close.clicked.connect(self.close)
        h.addWidget(mini); h.addWidget(close)
        bar.mousePressEvent = self._bar_press
        bar.mouseMoveEvent = self._bar_move
        return bar

    def _bar_press(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def _bar_move(self, e):
        if self._drag and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag)

    def showEvent(self, e):
        super().showEvent(e)
        apply_acrylic(self)

    # ----------------------------- login ------------------------------ #
    def _login_page(self) -> QWidget:
        # A fixed-width card centered both horizontally and vertically.
        page = QWidget()
        outer_v = QVBoxLayout(page); outer_v.setContentsMargins(0, 0, 0, 0)
        outer_v.addStretch(1)
        row_h = QHBoxLayout(); row_h.addStretch(1)

        card = QFrame(); card.setObjectName("LoginCard"); card.setFixedWidth(380)
        c = QVBoxLayout(card); c.setContentsMargins(34, 30, 34, 30); c.setSpacing(10)
        c.setAlignment(Qt.AlignmentFlag.AlignTop)

        logo = QLabel(); logo.setPixmap(svg_pixmap(MARK_SVG, 72))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c.addWidget(logo)
        name = QLabel("EASY PHONE UNLOCK"); name.setObjectName("Brand")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tag = QLabel("MTK Universal Tool"); tag.setObjectName("Sub")
        tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c.addWidget(name); c.addWidget(tag); c.addSpacing(16)

        self.in_user = QLineEdit(); self.in_user.setPlaceholderText("Username")
        self.in_pass = QLineEdit(); self.in_pass.setPlaceholderText("Password")
        self.in_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.in_pass.returnPressed.connect(self._do_login)
        c.addWidget(self.in_user); c.addWidget(self.in_pass)

        btn_login = QPushButton("Sign In"); btn_login.setObjectName("Primary")
        btn_login.clicked.connect(self._do_login)
        c.addSpacing(4); c.addWidget(btn_login)
        btn_reg = QPushButton("Create account"); btn_reg.clicked.connect(self._do_register)
        c.addWidget(btn_reg)

        self.login_msg = QLabel(""); self.login_msg.setObjectName("Sub")
        self.login_msg.setAlignment(Qt.AlignmentFlag.AlignCenter); self.login_msg.setWordWrap(True)
        c.addSpacing(6); c.addWidget(self.login_msg)
        self.hwid_lbl = QLabel(f"PC ID: {self.lic.hwid}"); self.hwid_lbl.setObjectName("Hint")
        self.hwid_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c.addWidget(self.hwid_lbl)

        row_h.addWidget(card); row_h.addStretch(1)
        outer_v.addLayout(row_h); outer_v.addStretch(1)
        return page

    def _do_login(self):
        r = self.lic.login(self.in_user.text().strip(), self.in_pass.text())
        if r.get("status") == "success":
            self._enter_dashboard()
        else:
            self.login_msg.setText(r.get("detail") or r.get("message") or "Login failed.")

    def _do_register(self):
        r = self.lic.register(self.in_user.text().strip(), self.in_pass.text())
        self.login_msg.setText(r.get("message") or r.get("detail") or "Registered.")

    # --------------------------- dashboard ---------------------------- #
    def _dashboard_page(self) -> QWidget:
        page = QWidget(); grid = QGridLayout(page)
        grid.setContentsMargins(20, 10, 20, 20); grid.setHorizontalSpacing(18)

        top = QHBoxLayout()
        self.welcome = QLabel("Welcome"); self.welcome.setObjectName("H1")
        self.credits_lbl = QLabel("Credits: -"); self.credits_lbl.setProperty("class", "badge")
        top.addWidget(self.welcome); top.addStretch(1); top.addWidget(self.credits_lbl)
        logout = QPushButton("Logout"); logout.setObjectName("Chip"); logout.clicked.connect(self._logout)
        top.addSpacing(12); top.addWidget(logout)
        grid.addLayout(top, 0, 0, 1, 2)

        def section(text):
            lbl = QLabel(text); lbl.setObjectName("SectionTitle"); return lbl

        # Left panel — Step 1 device, Step 2 firmware, Step 3 operations
        left = QVBoxLayout(); left.setSpacing(6)
        left.addWidget(section("1 · Device"))
        left.addWidget(QLabel("Brand"))
        self.cb_brand = QComboBox(); self.cb_brand.addItems(devices.brands())
        self.cb_brand.currentTextChanged.connect(self._brand_changed)
        left.addWidget(self.cb_brand)
        left.addWidget(QLabel("Model"))
        self.cb_model = QComboBox(); self.cb_model.currentTextChanged.connect(self._model_changed)
        left.addWidget(self.cb_model)
        btn_read = QPushButton("\U0001F50C  Read Device Info"); btn_read.setObjectName("Primary")
        btn_read.clicked.connect(self._read_info)
        left.addSpacing(2); left.addWidget(btn_read)
        self.info_lbl = QLabel("Device: not connected"); self.info_lbl.setObjectName("Sub")
        self.info_lbl.setWordWrap(True); self.info_lbl.setTextFormat(Qt.TextFormat.RichText)
        left.addWidget(self.info_lbl)

        left.addSpacing(10); left.addWidget(section("2 · Firmware"))
        btn_fw = QPushButton("\U0001F4C1  Load Scatter / OFP File")
        btn_fw.clicked.connect(self._load_firmware)
        left.addWidget(btn_fw)
        self.fw_lbl = QLabel("No firmware loaded"); self.fw_lbl.setObjectName("Sub"); self.fw_lbl.setWordWrap(True)
        left.addWidget(self.fw_lbl)

        left.addSpacing(10); left.addWidget(section("3 · Operations"))
        self.ops_box = QVBoxLayout(); self.ops_box.setSpacing(6); left.addLayout(self.ops_box)
        left.addStretch(1)

        left.addWidget(section("Speed"))
        self.slider = QSlider(Qt.Orientation.Horizontal); self.slider.setRange(1, 10); self.slider.setValue(6)
        left.addWidget(self.slider)

        left_w = QWidget(); left_w.setLayout(left); left_w.setFixedWidth(310)
        grid.addWidget(left_w, 1, 0)

        # Right panel: partition table (also the live display) + console + progress
        right = QVBoxLayout()
        right.addWidget(section("Partitions / Live Operation"))
        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 34)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        right.addWidget(self.table, 2)
        self.console = QPlainTextEdit(); self.console.setReadOnly(True)
        right.addWidget(self.console, 2)
        self.progress = QProgressBar(); self.progress.setValue(0)
        right.addWidget(self.progress)
        right_w = QWidget(); right_w.setLayout(right)
        grid.addWidget(right_w, 1, 1)
        grid.setColumnStretch(1, 1)
        return page

    def _enter_dashboard(self):
        self.welcome.setText(f"Welcome, {self.lic.user_data.get('username', '')}")
        self._refresh_credits()
        # Pull the latest chip/device catalog from the server (falls back to bundled).
        sync = self.lic.sync_catalog()
        self.cb_brand.blockSignals(True)
        self.cb_brand.clear(); self.cb_brand.addItems(devices.brands())
        self.cb_brand.blockSignals(False)
        if self.cb_brand.count():
            self._brand_changed(self.cb_brand.currentText())
        self.stack.setCurrentIndex(1)
        self._log("info", f"Logged in. PC ID {self.lic.hwid} registered to the server.")
        self._log("info", f"Catalog: {len(devices.brands())} brands, "
                          f"{sum(len(devices.models(b)) for b in devices.brands())} models. {sync.get('catalog')}")

    def _refresh_credits(self):
        self.credits_lbl.setText(f"Credits: {self.lic.credits}")

    def _logout(self):
        self.stack.setCurrentIndex(0); self.login_msg.setText("Logged out.")

    def _brand_changed(self, brand):
        self.cb_model.clear(); self.cb_model.addItems(devices.models(brand))

    def _model_changed(self, model):
        brand = self.cb_brand.currentText()
        if not model:
            return
        info = devices.model_info(brand, model)
        while self.ops_box.count():
            item = self.ops_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for op in devices.operations_for(brand, model):
            btn = QPushButton(devices.label(op))
            if op in SENSITIVE:
                btn.setObjectName("Danger")
            btn.clicked.connect(lambda _, o=op: self._start_operation(o))
            self.ops_box.addWidget(btn)

    # --------------------------- device info -------------------------- #
    def _read_info(self):
        if self.info_worker and self.info_worker.isRunning():
            return
        self.info_lbl.setText("Device: reading...")
        self._log("info", "Reading device info over BROM...")
        self.info_worker = DeviceInfoWorker()
        self.info_worker.log.connect(self._log)
        self.info_worker.info.connect(self._on_info)
        self.info_worker.done.connect(self._on_info_done)
        self.info_worker.start()

    def _on_info(self, data: dict):
        self.device_info = data
        self.info_lbl.setText(
            f"<b>{data['chip']}</b> on {data['port']}<br>"
            f"HW {data['hw_code']} • SWver {data['sw_ver']} • "
            f"{data['arch']} • sec {data['security']}"
        )
        # Safety: compare detected chip with the selected model's chip.
        model_chip = devices.model_info(self.cb_brand.currentText(), self.cb_model.currentText()).get("chip")
        if model_chip and data["chip"] != model_chip and not data["chip"].startswith("UNKNOWN"):
            self._log("warn", f"Detected {data['chip']} but model expects {model_chip}. Check your selection.")

    def _on_info_done(self, ok, message):
        if not ok:
            self.info_lbl.setText(f"Device: {message}")
            self._log("err", message)

    # --------------------------- firmware ----------------------------- #
    def _load_firmware(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select scatter / flash file", "",
            "Flash files (*scatter*.txt *.xml *.yaml *.ofp *.ozip);;All files (*.*)")
        if not path:
            return
        if self.fw_worker and self.fw_worker.isRunning():
            return
        from src.core.paths import cache_dir
        extract_root = f"{cache_dir()}/firmware"
        self.fw_lbl.setText("Loading firmware...")
        self._log("info", f"Loading {path.split('/')[-1]} ...")
        self.fw_worker = FirmwareLoadWorker(path, extract_root)
        self.fw_worker.log.connect(self._log)
        self.fw_worker.done.connect(self._on_firmware_loaded)
        self.fw_worker.start()

    def _on_firmware_loaded(self, fw, error):
        if error or fw is None:
            self.fw_lbl.setText("Firmware load failed")
            QMessageBox.critical(self, "Firmware error", error or "Unknown error")
            self._log("err", f"Firmware load failed: {error}")
            return
        import os
        self.scatter_partitions = fw.partitions
        self.firmware_dir = fw.extract_dir or (os.path.dirname(fw.scatter_path) if fw.scatter_path else "")
        self.fw_lbl.setText(f"[{fw.format.upper()}] {len(fw.partitions)} partitions loaded")
        self._log("ok", f"Firmware loaded ({fw.format.upper()}): {len(fw.partitions)} partitions.")
        for n in fw.notes:
            self._log("warn", n)
        self._populate_partitions()

    def _populate_partitions(self):
        self.table.setRowCount(0)
        for p in self.scatter_partitions:
            r = self.table.rowCount(); self.table.insertRow(r)
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk.setCheckState(Qt.CheckState.Checked if p.is_download else Qt.CheckState.Unchecked)
            self.table.setItem(r, 0, chk)
            self.table.setItem(r, 1, QTableWidgetItem(p.name))
            self.table.setItem(r, 2, QTableWidgetItem(p.file_name))
            self.table.setItem(r, 3, QTableWidgetItem(f"0x{p.partition_size:X}"))
            self.table.setItem(r, 4, QTableWidgetItem("-"))

    def _checked_flash_steps(self):
        """Return [{partition,file,start,size}] for checked, downloadable rows.
        File is resolved to an absolute path under the firmware directory."""
        import os
        by_name = {p.name: p for p in self.scatter_partitions}
        steps = []
        for r in range(self.table.rowCount()):
            if self.table.item(r, 0).checkState() != Qt.CheckState.Checked:
                continue
            name = self.table.item(r, 1).text()
            fname = self.table.item(r, 2).text()
            if not fname or fname.upper() == "NONE":
                continue
            p = by_name.get(name)
            fpath = fname
            if not os.path.isabs(fpath) and self.firmware_dir:
                fpath = os.path.join(self.firmware_dir, fname)
            steps.append({
                "partition": name, "file": fpath,
                "start": p.linear_start if p else 0,
                "size": p.partition_size if p else 0,
            })
        return steps

    # --------------------------- operations --------------------------- #
    def _start_operation(self, operation):
        if self.worker and self.worker.isRunning():
            return
        brand = self.cb_brand.currentText(); model = self.cb_model.currentText()
        chip = devices.model_info(brand, model).get("chip", "")
        imei = serial = ""; consent = False
        flash_steps = []
        erase_targets = []

        if operation == "FLASH_FIRMWARE":
            flash_steps = self._checked_flash_steps()
            if not flash_steps:
                QMessageBox.information(self, "No firmware",
                                        "Load a scatter/OFP file and tick the partitions to flash first.")
                return
        elif operation == "FRP_RESET":
            erase_targets = ["frp", "metadata"]

        if operation in SENSITIVE:
            dlg = ConsentDialog(self, devices.label(operation))
            if dlg.exec() != QDialog.DialogCode.Accepted:
                self._log("warn", f"{devices.label(operation)} cancelled by operator.")
                return
            imei, serial, consent = dlg.values()

        # Protected-partition safety confirmation (from the real targets).
        targets = [s["partition"] for s in flash_steps] + erase_targets
        protected = [p for p in targets if is_protected(p)]
        if protected:
            msg = ("These PROTECTED partitions will be modified:\n  - "
                   + "\n  - ".join(sorted(set(protected)))
                   + "\n\nA wrong file here can brick the device. A backup is taken first. Continue?")
            if QMessageBox.question(self, "Safety confirmation", msg) != QMessageBox.StandardButton.Yes:
                self._log("warn", "Operation aborted at safety confirmation.")
                return

        if operation != "FLASH_FIRMWARE":
            self.table.setRowCount(0)
        self.progress.setValue(0)
        self._log("info", f"=== {devices.label(operation)} :: {brand} {model} [{chip}] ===")

        self.worker = OperationWorker(
            self.lic, operation, devices.payloads_for(operation),
            brand, model, chip, imei, serial, consent, confirm_cb=lambda m: True,
            flash_steps=flash_steps, erase_targets=erase_targets,
        )
        self.worker.log.connect(self._log)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.action.connect(self._on_action)
        self.worker.finished_op.connect(self._on_finished)
        self.worker.start()

    def _on_action(self, partition, action, filename, state):
        # Update the matching partition row's State; add a row if not present.
        for r in range(self.table.rowCount()):
            if self.table.item(r, 1) and self.table.item(r, 1).text() == partition:
                self.table.item(r, 4).setText(state)
                if self.table.item(r, 2) and not self.table.item(r, 2).text():
                    self.table.item(r, 2).setText(filename)
                return
        r = self.table.rowCount(); self.table.insertRow(r)
        self.table.setItem(r, 0, QTableWidgetItem(""))
        self.table.setItem(r, 1, QTableWidgetItem(partition))
        self.table.setItem(r, 2, QTableWidgetItem(filename))
        self.table.setItem(r, 3, QTableWidgetItem("-"))
        self.table.setItem(r, 4, QTableWidgetItem(state))

    def _on_finished(self, ok, message, remaining):
        self._log("ok" if ok else "err", message)
        if remaining is not None:
            self.lic.user_data["credits"] = remaining
            self._refresh_credits()

    def _log(self, level, message):
        colors = {"info": "#9aa0c8", "step": "#8be9fd", "ok": "#50fa7b", "warn": "#ffb86c", "err": "#ff5a6e"}
        c = colors.get(level, "#eef0ff")
        self.console.appendHtml(f'<span style="color:{c}">{message}</span>')
