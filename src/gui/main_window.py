"""Main application window: glass UI, login, brand/model ops, live display."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFrame, QGraphicsDropShadowEffect,
    QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPlainTextEdit,
    QProgressBar, QPushButton, QSlider, QStackedWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from src.auth.license_client import LicenseClient
from src.core import devices
from src.core.safety import is_protected
from src.gui.theme import QSS, apply_acrylic
from src.gui.worker import WORKFLOWS, OperationWorker

SENSITIVE = {"FRP_RESET", "NETWORK_UNLOCK", "IMEI_REPAIR", "BOOTLOADER_UNLOCK", "BACKUP_SECURITY"}
SERVER_DEFAULT = "http://127.0.0.1:8000"


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
    def __init__(self, server_url: str = SERVER_DEFAULT):
        super().__init__()
        self.setObjectName("Root")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(1040, 660)
        self._drag = None
        self.worker: OperationWorker | None = None

        self.lic = LicenseClient(server_url=server_url)

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
        h = QHBoxLayout(bar); h.setContentsMargins(18, 0, 12, 0)
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
        page = QWidget(); v = QVBoxLayout(page); v.setContentsMargins(60, 20, 60, 40)
        v.addStretch(1)
        h1 = QLabel("Sign in"); h1.setObjectName("H1")
        sub = QLabel("Your PC ID and IP are registered to your account on login."); sub.setObjectName("Sub")
        v.addWidget(h1); v.addWidget(sub); v.addSpacing(14)

        self.in_user = QLineEdit(); self.in_user.setPlaceholderText("Username")
        self.in_pass = QLineEdit(); self.in_pass.setPlaceholderText("Password")
        self.in_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.in_pass.returnPressed.connect(self._do_login)
        v.addWidget(self.in_user); v.addWidget(self.in_pass)

        row = QHBoxLayout()
        btn_login = QPushButton("Sign In"); btn_login.setObjectName("Primary")
        btn_login.clicked.connect(self._do_login)
        btn_reg = QPushButton("Register"); btn_reg.clicked.connect(self._do_register)
        row.addWidget(btn_login, 2); row.addWidget(btn_reg, 1)
        v.addSpacing(6); v.addLayout(row)

        self.login_msg = QLabel(""); self.login_msg.setObjectName("Sub")
        v.addWidget(self.login_msg)
        self.hwid_lbl = QLabel(f"HWID: {self.lic.hwid}"); self.hwid_lbl.setObjectName("Sub")
        v.addSpacing(8); v.addWidget(self.hwid_lbl)
        v.addStretch(2)
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

        # Top bar
        top = QHBoxLayout()
        self.welcome = QLabel("Welcome"); self.welcome.setObjectName("H1")
        self.credits_lbl = QLabel("Credits: -"); self.credits_lbl.setProperty("class", "badge")
        top.addWidget(self.welcome); top.addStretch(1); top.addWidget(self.credits_lbl)
        logout = QPushButton("Logout"); logout.setObjectName("Chip"); logout.clicked.connect(self._logout)
        top.addSpacing(12); top.addWidget(logout)
        grid.addLayout(top, 0, 0, 1, 2)

        # Left: device + operations
        left = QVBoxLayout()
        left.addWidget(QLabel("Brand"))
        self.cb_brand = QComboBox(); self.cb_brand.addItems(devices.brands())
        self.cb_brand.currentTextChanged.connect(self._brand_changed)
        left.addWidget(self.cb_brand)
        left.addWidget(QLabel("Model"))
        self.cb_model = QComboBox(); self.cb_model.currentTextChanged.connect(self._model_changed)
        left.addWidget(self.cb_model)
        self.chip_lbl = QLabel("Chip: -"); self.chip_lbl.setObjectName("Sub")
        left.addWidget(self.chip_lbl)

        left.addWidget(QLabel("I/O Speed"))
        self.slider = QSlider(Qt.Orientation.Horizontal); self.slider.setRange(1, 10); self.slider.setValue(6)
        left.addWidget(self.slider)

        left.addSpacing(6)
        self.ops_box = QVBoxLayout(); left.addLayout(self.ops_box)
        left.addStretch(1)
        left_w = QWidget(); left_w.setLayout(left); left_w.setFixedWidth(300)
        grid.addWidget(left_w, 1, 0)

        # Right: live display
        right = QVBoxLayout()
        right.addWidget(QLabel("Live Operation"))
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Partition", "Action", "File", "State"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        right.addWidget(self.table, 2)
        self.console = QPlainTextEdit(); self.console.setReadOnly(True)
        right.addWidget(self.console, 3)
        self.progress = QProgressBar(); self.progress.setValue(0)
        right.addWidget(self.progress)
        right_w = QWidget(); right_w.setLayout(right)
        grid.addWidget(right_w, 1, 1)
        grid.setColumnStretch(1, 1)
        return page

    def _enter_dashboard(self):
        u = self.lic.user_data
        self.welcome.setText(f"Welcome, {u.get('username', '')}")
        self._refresh_credits()
        if self.cb_brand.count():
            self._brand_changed(self.cb_brand.currentText())
        self.stack.setCurrentIndex(1)
        self._log("info", f"Logged in. PC ID {self.lic.hwid} registered to the server.")

    def _refresh_credits(self):
        self.credits_lbl.setText(f"Credits: {self.lic.credits}")

    def _logout(self):
        self.stack.setCurrentIndex(0); self.login_msg.setText("Logged out.")

    def _brand_changed(self, brand):
        self.cb_model.clear()
        self.cb_model.addItems(devices.models(brand))

    def _model_changed(self, model):
        brand = self.cb_brand.currentText()
        if not model:
            return
        info = devices.model_info(brand, model)
        self.chip_lbl.setText(f"Chip: {info.get('chip', '-')}")
        # Rebuild operation buttons for this model.
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

    # --------------------------- operations --------------------------- #
    def _start_operation(self, operation):
        if self.worker and self.worker.isRunning():
            return
        brand = self.cb_brand.currentText(); model = self.cb_model.currentText()
        imei = serial = ""; consent = False

        if operation in SENSITIVE:
            dlg = ConsentDialog(self, devices.label(operation))
            if dlg.exec() != QDialog.DialogCode.Accepted:
                self._log("warn", f"{devices.label(operation)} cancelled by operator.")
                return
            imei, serial, consent = dlg.values()

        # Protected-partition safety confirmation, collected on the GUI thread.
        protected = [p for (p, a) in WORKFLOWS.get(operation, []) if is_protected(p)]
        if protected:
            from PyQt6.QtWidgets import QMessageBox
            msg = ("These PROTECTED partitions will be modified:\n  - "
                   + "\n  - ".join(sorted(set(protected)))
                   + "\n\nA wrong file here can brick the device. A backup is taken first. Continue?")
            if QMessageBox.question(self, "Safety confirmation", msg) != QMessageBox.StandardButton.Yes:
                self._log("warn", "Operation aborted at safety confirmation.")
                return

        self.table.setRowCount(0); self.progress.setValue(0)
        self._log("info", f"=== {devices.label(operation)} :: {brand} {model} ===")

        self.worker = OperationWorker(
            self.lic, operation, devices.payloads_for(operation),
            brand, model, imei, serial, consent, confirm_cb=lambda m: True,
        )
        self.worker.log.connect(self._log)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.action.connect(self._on_action)
        self.worker.finished_op.connect(self._on_finished)
        self.worker.start()

    def _on_action(self, partition, action, filename, state):
        # Update the row for this partition or add a new one.
        for r in range(self.table.rowCount()):
            if self.table.item(r, 0).text() == partition and self.table.item(r, 3).text() != "DONE":
                self.table.item(r, 3).setText(state)
                return
        r = self.table.rowCount(); self.table.insertRow(r)
        for c, val in enumerate([partition, action, filename, state]):
            self.table.setItem(r, c, QTableWidgetItem(val))

    def _on_finished(self, ok, message, remaining):
        self._log("ok" if ok else "err", message)
        if remaining is not None:
            self.lic.user_data["credits"] = remaining
            self._refresh_credits()

    def _log(self, level, message):
        colors = {"info": "#9aa0c8", "step": "#8be9fd", "ok": "#50fa7b", "warn": "#ffb86c", "err": "#ff5a6e"}
        c = colors.get(level, "#eef0ff")
        self.console.appendHtml(f'<span style="color:{c}">{message}</span>')
