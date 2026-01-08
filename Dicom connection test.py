import sys
import os
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QGridLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QFileDialog, QSpinBox, QHBoxLayout
)
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from pynetdicom import AE
try:
    
    from pynetdicom import StoragePresentationContexts as STORAGE_CONTEXTS
except Exception:
    try:
        from pynetdicom import AllStoragePresentationContexts as STORAGE_CONTEXTS
    except Exception:
        STORAGE_CONTEXTS = None

import pydicom
from pydicom.uid import ImplicitVRLittleEndian, ExplicitVRLittleEndian, ExplicitVRBigEndian


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = Path(__file__).resolve().parent
    return str(Path(base_path) / relative_path)


class DICOMTestSender(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowIcon(QIcon(resource_path("assets/icon.ico")))

        self.setWindowTitle("DICOM connection Test (C-ECHO & C-STORE)")
        self.setMinimumWidth(600)
        self._build_ui()        

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        grid = QGridLayout(central)
        row = 0

      
        grid.addWidget(QLabel("Host/IP:"), row, 0)
        self.host_edit = QLineEdit("127.0.0.1")
        grid.addWidget(self.host_edit, row, 1, 1, 2)
        row += 1

      
        grid.addWidget(QLabel("Port:"), row, 0)
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(1124)  
        grid.addWidget(self.port_spin, row, 1, 1, 2)
        row += 1


        grid.addWidget(QLabel("Called AE Title (Server):"), row, 0)
        self.called_ae_edit = QLineEdit("server AE")
        grid.addWidget(self.called_ae_edit, row, 1, 1, 2)
        row += 1

      
        grid.addWidget(QLabel("Calling AE Title (This client):"), row, 0)
        self.calling_ae_edit = QLineEdit("your AE")
        grid.addWidget(self.calling_ae_edit, row, 1, 1, 2)
        row += 1

  
        grid.addWidget(QLabel("DICOM file:"), row, 0)
        self.file_edit = QLineEdit()
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_file)
        file_layout = QHBoxLayout()
        file_layout.addWidget(self.file_edit)
        file_layout.addWidget(browse_btn)
        grid.addLayout(file_layout, row, 1, 1, 2)
        row += 1


        self.echo_btn = QPushButton("Send C-ECHO (Ping)")
        self.echo_btn.clicked.connect(self.send_echo)
        grid.addWidget(self.echo_btn, row, 1)

        self.store_btn = QPushButton("Send C-STORE (Send DICOM)")
        self.store_btn.clicked.connect(self.send_store)
        grid.addWidget(self.store_btn, row, 2)
        row += 1


        grid.addWidget(QLabel("Log:"), row, 0, Qt.AlignmentFlag.AlignTop)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        grid.addWidget(self.log_text, row, 1, 1, 2)
        
        row += 1

        powered_label = QLabel("powered by: <b>sasan zare</b>")
        powered_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        powered_label.setStyleSheet("color: gray; font-size: 10pt;")
        grid.addWidget(powered_label, row, 2, Qt.AlignmentFlag.AlignRight)

    def log(self, msg: str):
        self.log_text.append(msg)

    def browse_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select DICOM file", "", "DICOM Files (*.dcm);;All Files (*)")
        if path:
            self.file_edit.setText(path)

    def send_echo(self):
        host = self.host_edit.text().strip()
        port = int(self.port_spin.value())
        called_ae = self.called_ae_edit.text().strip() or "ANY-SCP"
        calling_ae = self.calling_ae_edit.text().strip() or "TEST"

        self.log(f"> C-ECHO to {host}:{port} (Called AE: {called_ae}, Calling AE: {calling_ae})")
        try:
            ae = AE(ae_title=calling_ae)
        
            ae.add_requested_context('1.2.840.10008.1.1')

            assoc = ae.associate(host, port, ae_title=called_ae)
            if assoc.is_established:
                status = assoc.send_c_echo()
                code = getattr(status, "Status", status)
                self.log(f"  C-ECHO Response: 0x{int(code):04X}")
                assoc.release()
            else:
                self.log("  Association failed.")
        except Exception as e:
            self.log(f"  ERROR: {type(e).__name__}: {e}")

    def _add_storage_contexts(self, ae: AE, ds):
        """
        Try to add broad storage presentation contexts; fall back to dataset's SOP Class with common TSs.
        """
        if STORAGE_CONTEXTS:
            for cx in STORAGE_CONTEXTS:
                try:
                    ae.add_requested_context(cx.abstract_syntax)
                except Exception:
                    pass
            return

       
        ts_list = [ImplicitVRLittleEndian, ExplicitVRLittleEndian, ExplicitVRBigEndian]
        try:
            ts_uid = getattr(getattr(ds, "file_meta", None), "TransferSyntaxUID", None)
            if ts_uid and str(ts_uid) not in [str(u) for u in ts_list]:
                ts_list.append(ts_uid)
        except Exception:
            pass

        sop = getattr(ds, "SOPClassUID", None)
        if sop:
            ae.add_requested_context(str(sop), [str(u) for u in ts_list])

    def send_store(self):
        host = self.host_edit.text().strip()
        port = int(self.port_spin.value())
        called_ae = self.called_ae_edit.text().strip() or "ANY-SCP"
        calling_ae = self.calling_ae_edit.text().strip() or "TEST"
        fpath = self.file_edit.text().strip()

        if not fpath or not Path(fpath).exists():
            self.log("  Please choose a valid DICOM file.")
            return

        self.log(f"> C-STORE to {host}:{port} (Called AE: {called_ae}, Calling AE: {calling_ae})")
        try:
            ds = pydicom.dcmread(fpath, force=True)
            ae = AE(ae_title=calling_ae)

         
            self._add_storage_contexts(ae, ds)

            assoc = ae.associate(host, port, ae_title=called_ae)
            if assoc.is_established:
                status = assoc.send_c_store(ds)
                code = getattr(status, "Status", status)
                self.log(f"  C-STORE Response: 0x{int(code):04X}")
                assoc.release()
            else:
                self.log("  Association failed.")
        except Exception as e:
            self.log(f"  ERROR: {type(e).__name__}: {e}")


def main():
    app = QApplication(sys.argv)
    win = DICOMTestSender()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
