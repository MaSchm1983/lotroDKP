import sys, json, os, requests
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QDialog, QLineEdit, QLabel, QComboBox, QMessageBox, QSpinBox, QFileDialog, QListWidget, QListWidgetItem, QCheckBox
)
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtCore import Qt, QSize, QByteArray, QBuffer

# --- Utility: download and cache icons ---
ICON_CACHE = {}
COL_WIDTH = [40, 50, 100, 60, 160, 80]
COL_WIDTH_DKP = [110, 120, 120]     # Player | Awarded | Spent (adjust as you like)
COL_WIDTH_LOOT = [90, 110, 210]     # Date | Player | Item (Price)
WIN_PAD = 28 # 14px left + 14px right, for example
#SCROLLBAR_WIDTH = 20 


def resource_path(relative_path):
    # For PyInstaller compatibility (works in dev and packaged)
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def get_icon(path_or_url):
    if not path_or_url:
        return QIcon()
    if path_or_url in ICON_CACHE:
        return ICON_CACHE[path_or_url]
    if path_or_url.startswith("http"):
        # Download from URL
        try:
            img_data = requests.get(path_or_url, timeout=8).content
            pix = QPixmap()
            pix.loadFromData(img_data)
            icon = QIcon(pix)
            ICON_CACHE[path_or_url] = icon
            return icon
        except Exception:
            return QIcon()
    else:
        # Local file
        if os.path.exists(path_or_url):
            icon = QIcon(path_or_url)
            ICON_CACHE[path_or_url] = icon
            return icon
        return QIcon()

# --- Main App ---
class DKPManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Die Ritters von Rohan DKP Helegrod")
        app = QApplication.instance() or QApplication([])
        SCROLLBAR_WIDTH = app.style().pixelMetric(QApplication.style().PM_ScrollBarExtent)
        total_width = sum(COL_WIDTH) + WIN_PAD + SCROLLBAR_WIDTH
        self.setFixedWidth(total_width)
        
        self.resize(total_width, 880)
        self.lotro_classes = [
            "Burglar", "Captain", "Champion", "Guardian", "Hunter", "Loremaster", "Minstrel"
        ]
        self.class_icons = {
            "Burglar": resource_path("images/Framed_Burglar-icon.png"),
            "Captain": resource_path("images/Framed_Captain-icon.png"),
            "Champion": resource_path("images/Framed_Champion-icon.png"),
            "Guardian": resource_path("images/Framed_Guardian-icon.png"),
            "Hunter": resource_path("images/Framed_Hunter-icon.png"),
            "Loremaster": resource_path("images/Framed_Lore-master-icon.png"),
            "Minstrel": resource_path("images/Framed_Minstrel-icon.png")
        }
        self.items_db = []
        self.players = {}
        self.dkp_history = []
        self.dkp_file_path = None
        self.items_file_path = resource_path("content/items.json")
        self.init_ui()
        self.load_items()
        self.load_dkp(resource_path("lotro_dkp_backup.json"))

    def init_ui(self):
        vbox = QVBoxLayout(self)

        # Button row
        btnrow = QHBoxLayout()
        self.add_btn = QPushButton("Add Player")
        self.award_btn = QPushButton("Award DKP")
        self.spend_btn = QPushButton("Spend DKP")
        self.beryl_btn = QPushButton("Add Beryl Shard")
        self.remove_btn = QPushButton("Remove Player")
        #self.open_btn = QPushButton("Open DKP File")
        #self.save_btn = QPushButton("Save DKP File")
        btnrow.addWidget(self.add_btn)
        btnrow.addWidget(self.award_btn)
        btnrow.addWidget(self.spend_btn)
        btnrow.addWidget(self.beryl_btn)
        btnrow.addWidget(self.remove_btn)
        #btnrow.addWidget(self.open_btn)
        #btnrow.addWidget(self.save_btn)
        vbox.addLayout(btnrow)


        # ---- FILTER by class section ----
        filter_row = QHBoxLayout()
        filter_label = QLabel("Filter by class:")
        filter_row.addWidget(filter_label)
        filter_row.setContentsMargins(6, 8, 0, 8)
        self.filter_combo = QComboBox()
        self.filter_combo.addItem("--all--")
        for c in self.lotro_classes:
            self.filter_combo.addItem(c)
        filter_row.addWidget(self.filter_combo)
        filter_row.addStretch()  # Pushes the dropdown to the left

        vbox.addLayout(filter_row)

        self.filter_combo.currentIndexChanged.connect(self.refresh_table)
        
        # Table
        app = QApplication.instance() or QApplication([])
        SCROLLBAR_WIDTH = app.style().pixelMetric(QApplication.style().PM_ScrollBarExtent)
        self.table = QTableWidget(0, len(COL_WIDTH))        
        for col, width in enumerate(COL_WIDTH):
            self.table.setColumnWidth(col, width)
        self.table.setHorizontalHeaderLabels(["#", "Class", "Name", "DKP", "Loot", "Beryl shard"])
 
        for i in range(self.table.columnCount()):
            item = self.table.horizontalHeaderItem(i)
            if item:
                item.setTextAlignment(Qt.AlignCenter)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(self.table.SelectRows)
        self.table.setEditTriggers(self.table.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setFixedWidth(sum(COL_WIDTH) + SCROLLBAR_WIDTH)
        self.table.setIconSize(QSize(24, 24))
        vbox.addWidget(self.table)
        
        # History buttons row
        hist_btn_row = QHBoxLayout()
        self.dkp_hist_btn = QPushButton("Show DKP History")
        self.loot_hist_btn = QPushButton("Show Loot History")
        hist_btn_row.addWidget(self.dkp_hist_btn)
        hist_btn_row.addWidget(self.loot_hist_btn)
        vbox.addLayout(hist_btn_row)

        # Connect buttons
        self.add_btn.clicked.connect(self.show_add_player)
        self.award_btn.clicked.connect(self.show_award_dkp)
        self.spend_btn.clicked.connect(self.show_spend_dkp)
        self.beryl_btn.clicked.connect(self.show_add_beryl)
        self.remove_btn.clicked.connect(self.show_remove_player)
        self.dkp_hist_btn.clicked.connect(self.show_dkp_history)
        self.loot_hist_btn.clicked.connect(self.show_loot_history)
        #self.open_btn.clicked.connect(self.open_dkp_file)
        #self.save_btn.clicked.connect(self.save_dkp_file)
        


    def load_items(self):
        try:
            with open(self.items_file_path, "r", encoding="utf-8") as f:
                self.items_db = json.load(f)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not load items.json!\n{e}")
            self.items_db = []

    def load_dkp(self, path=None):
        fn = path or self.dkp_file_path or resource_path("lotro_dkp_backup.json")
        if not os.path.exists(fn):
            self.players = {}
            self.dkp_history = []
            self.refresh_table()
            return
        try:
            with open(fn, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.players = data["players"] if "players" in data else data
                self.dkp_history = data.get("DKP_HISTORY", [])
                self.dkp_file_path = fn
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not load DKP file!\n{e}")
            self.players = {}
            self.dkp_history = []
        self.refresh_table()

    def save_dkp_file(self):
        path = self.dkp_file_path or resource_path("lotro_dkp_backup.json")
        try:
            data = {
                "players": self.players,
                "DKP_HISTORY": self.dkp_history
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.dkp_file_path = path
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not save file!\n{e}")

    def open_dkp_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open DKP File", "", "JSON Files (*.json)")
        if path:
            self.load_dkp(path)

    def refresh_table(self):
        players = sorted(self.players.items(), key=lambda t: (-t[1].get("dkp", 0), t[0]))
        self.table.setRowCount(len(players))
        for row, (name, p) in enumerate(players):
            self.table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            # --- Class icon (local path)
            icon_path = self.class_icons.get(p.get("class", ""), "")
            icon = get_icon(icon_path)
            citem = QTableWidgetItem()
            citem.setIcon(icon)
            citem.setText("")
            self.table.setItem(row, 1, citem)
            pname_item = QTableWidgetItem(name)
            # --- Tooltip for twinks (with local class icons)
            twinks = p.get("Twinks", [])
            if twinks:
                tt_lines = []
                for idx, t in enumerate(twinks, 1):
                    tclass = t.get("class", "")
                    tname = t.get("name", "")
                    ticon_path = self.class_icons.get(tclass, "")
                    icon_html = ""
                    if ticon_path and os.path.exists(ticon_path):
                        ticon = QPixmap(ticon_path).scaled(15, 15, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        ba = QByteArray()
                        buffer = QBuffer(ba)
                        buffer.open(QBuffer.WriteOnly)
                        ticon.save(buffer, "PNG")
                        b64 = ba.toBase64().data().decode()
                        # icon after name, a little lower
                        icon_html = f' <img src="data:image/png;base64,{b64}" width="15" height="15" style="vertical-align:middle; margin-bottom:+5px;">'
                    else:
                        icon_html = f" [{tclass}]"
                    tt_lines.append(f"{idx}. {tname}{icon_html}")
                tooltip_html = "<b>Twinks:</b><br>" + "<br>".join(tt_lines)
                pname_item.setToolTip(tooltip_html)
            self.table.setItem(row, 2, pname_item)
            self.table.setItem(row, 3, QTableWidgetItem(str(p.get("dkp", 0))))
            self.table.setItem(row, 5, QTableWidgetItem(str(p.get("beryl_shards", 0))))
            # --- Loot icons (URLs!)
            loot = p.get("loot", [])[-5:]
            loot_widget = QWidget()
            loot_hbox = QHBoxLayout(loot_widget)
            loot_hbox.setContentsMargins(8, 0, 0, 0)
            loot_hbox.setSpacing(2)
            for l in loot:
                li = QLabel()
                icon_url = l.get("icon", "")
                if icon_url:
                    li.setPixmap(get_icon(icon_url).pixmap(24, 24))
                else:
                    li.setText("?")
                # Date formatting
                date_str = l.get("date", "")[:10]
                tip = f"{l.get('name','') or l.get('item','')}\n{l.get('cost','')} DKP\n{date_str}"
                li.setToolTip(tip)
                loot_hbox.addWidget(li)
            loot_widget.setLayout(loot_hbox)
            self.table.setCellWidget(row, 4, loot_widget)
            for col in [0, 1, 3, 5]:
                item = self.table.item(row, col)
                if item:
                    item.setTextAlignment(Qt.AlignCenter)
        self.table.resizeRowsToContents()

    def show_add_player(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Add Player or Twink")
        v = QVBoxLayout(dlg)
        name = QLineEdit()
        klass = QComboBox()
        klass.addItems(self.lotro_classes)
        v.addWidget(QLabel("Name:"))
        v.addWidget(name)
        v.addWidget(QLabel("Class:"))
        v.addWidget(klass)
        check_row = QHBoxLayout()
        main_cb = QCheckBox("Main")
        twink_cb = QCheckBox("Twink")
        main_cb.setChecked(True)
        check_row.addWidget(main_cb)
        check_row.addWidget(twink_cb)
        v.addLayout(check_row)
        main_dropdown = QComboBox()
        main_dropdown.setVisible(False)
        def refresh_main_dropdown():
            main_dropdown.clear()
            for pname in sorted(self.players.keys()):
                main_dropdown.addItem(pname)
        refresh_main_dropdown()
        v.addWidget(QLabel("Assign to main:"))
        v.addWidget(main_dropdown)
        main_dropdown.setVisible(False)

        def on_main_cb():
            if main_cb.isChecked():
                twink_cb.setChecked(False)
                main_dropdown.setVisible(False)
            else:
                if not twink_cb.isChecked():
                    main_cb.setChecked(True)
        def on_twink_cb():
            if twink_cb.isChecked():
                main_cb.setChecked(False)
                refresh_main_dropdown()
                main_dropdown.setVisible(True)
            else:
                if not main_cb.isChecked():
                    twink_cb.setChecked(True)
        main_cb.stateChanged.connect(on_main_cb)
        twink_cb.stateChanged.connect(on_twink_cb)

        btn = QPushButton("Add")
        v.addWidget(btn)
        btn.clicked.connect(dlg.accept)
        if dlg.exec_():
            pname = name.text().strip()
            pcl = klass.currentText()
            if not pname:
                return
            if main_cb.isChecked():
                # Normal main char add
                if pname in self.players:
                    return
                pdata = {"name": pname, "class": pcl, "dkp": 0, "loot": []}
                self.players[pname] = pdata
            elif twink_cb.isChecked():
                main_name = main_dropdown.currentText()
                if not main_name:
                    return
                if main_name in self.players:
                    if "Twinks" not in self.players[main_name]:
                        self.players[main_name]["Twinks"] = []
                    if pname not in self.players[main_name]["Twinks"]:
                        self.players[main_name]["Twinks"].append({"name": pname, "class": pcl})
            self.refresh_table()
            self.save_dkp_file()

    def show_remove_player(self):
        if not self.players:
            QMessageBox.information(self, "Info", "No players.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Remove Player")
        v = QVBoxLayout(dlg)
        combo = QComboBox()
        combo.addItems(sorted(self.players.keys()))
        v.addWidget(QLabel("Player:"))
        v.addWidget(combo)
        btn = QPushButton("Remove")
        v.addWidget(btn)
        btn.clicked.connect(dlg.accept)
        if dlg.exec_():
            pname = combo.currentText()
            if pname in sorted(self.players):
                del self.players[pname]
                self.refresh_table()
                self.save_dkp_file()

    def show_add_beryl(self):
        if not self.players:
            QMessageBox.information(self, "Info", "No players.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Add Beryl Shard")
        v = QVBoxLayout(dlg)
        label = QLabel("Players:")
        v.addWidget(label)
        playerlist = QListWidget()
        playerlist.setSelectionMode(QListWidget.MultiSelection)
        for pname in sorted(self.players):
            item = QListWidgetItem(pname)
            playerlist.addItem(item)
        v.addWidget(playerlist)
        count_label = QLabel("How many Beryl Shards?")
        v.addWidget(count_label)
        count_input = QSpinBox()
        count_input.setMinimum(1)
        count_input.setMaximum(99)
        count_input.setValue(1)
        v.addWidget(count_input)
        btn = QPushButton("Add Beryl Shard(s)")
        v.addWidget(btn)
        btn.clicked.connect(dlg.accept)
        if dlg.exec_():
            count = count_input.value()
            sel = playerlist.selectedItems()
            for item in sel:
                pname = item.text()
                self.players[pname].setdefault("beryl_shards", 0)
                self.players[pname]["beryl_shards"] += count
            self.refresh_table()
            self.save_dkp_file()


    def show_award_dkp(self):
        if not self.players:
            QMessageBox.information(self, "Info", "No players.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Award DKP")
        v = QVBoxLayout(dlg)
        label = QLabel("Players:")
        v.addWidget(label)
        playerlist = QListWidget()
        playerlist.setSelectionMode(QListWidget.MultiSelection)
        for pname in sorted(self.players):
            item = QListWidgetItem(pname)
            playerlist.addItem(item)
        v.addWidget(playerlist)
        dkp_label = QLabel("Add DKP:")
        v.addWidget(dkp_label)
        dkp_input = QSpinBox()
        dkp_input.setMinimum(1)
        dkp_input.setMaximum(9999)
        dkp_input.setValue(100)
        v.addWidget(dkp_input)
        btn = QPushButton("Award")
        v.addWidget(btn)
        btn.clicked.connect(dlg.accept)
        if dlg.exec_():
            pts = dkp_input.value()
            sel = playerlist.selectedItems()
            for item in sel:
                pname = item.text()
                self.players[pname]["dkp"] = self.players[pname].get("dkp",0) + pts
            self.refresh_table()
            self.save_dkp_file()

    def show_spend_dkp(self):
        if not self.players:
            QMessageBox.information(self, "Info", "No players.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Spend DKP")
        v = QVBoxLayout(dlg)
        pnamebox = QComboBox()
        pnames = sorted(self.players.keys())
        pnamebox.addItems(pnames)
        v.addWidget(QLabel("Player:"))
        v.addWidget(pnamebox)
        # Item dropdown
        itembox = QComboBox()
        for item in self.items_db:
            label = f"{item.get('name','')} ({item.get('set','')})"
            itembox.addItem(label, item)
        v.addWidget(QLabel("Item:"))
        v.addWidget(itembox)
        # DKP cost
        dkp_label = QLabel("DKP:")
        v.addWidget(dkp_label)
        dkp_input = QSpinBox()
        dkp_input.setMinimum(1)
        dkp_input.setMaximum(9999)
        dkp_input.setValue(100)
        v.addWidget(dkp_input)
        btn = QPushButton("Spend")
        v.addWidget(btn)
        btn.clicked.connect(dlg.accept)
        if dlg.exec_():
            pname = pnamebox.currentText()
            item = itembox.currentData()
            cost = dkp_input.value()
            if self.players[pname]["dkp"] < cost:
                QMessageBox.warning(self, "Not enough DKP!", f"{pname} has only {self.players[pname]['dkp']} DKP")
                return
            self.players[pname]["dkp"] -= cost
            loot = self.players[pname].setdefault("loot", [])
            entry = dict(item)
            entry["cost"] = cost
            import datetime
            entry["date"] = datetime.datetime.now().isoformat()
            loot.append(entry)
            self.refresh_table()
            self.save_dkp_file()

    def show_dkp_history(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("DKP History")
        layout = QVBoxLayout(dlg)
        table = QTableWidget(0, 3, dlg)
        table.setHorizontalHeaderLabels(["Player", "Awarded DKP", "Spent DKP"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(table.NoEditTriggers)
        table.setSelectionMode(table.NoSelection)
        
        # Set column widths
        for i, w in enumerate(COL_WIDTH_DKP):
            table.setColumnWidth(i, w)
        SCROLLBAR_WIDTH = app.style().pixelMetric(QApplication.style().PM_ScrollBarExtent)
        table.setFixedWidth(sum(COL_WIDTH_DKP) + SCROLLBAR_WIDTH)
        table.setMinimumHeight(300)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Fill table
        for name, p in sorted(self.players.items()):
            awarded = p.get("dkp", 0) + sum(l.get("cost", 0) for l in p.get("loot", []))
            spent = sum(l.get("cost", 0) for l in p.get("loot", []))
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(name))
            table.setItem(row, 1, QTableWidgetItem(str(awarded)))
            table.setItem(row, 2, QTableWidgetItem(str(spent)))
            # Center alignment for numbers
            table.item(row, 1).setTextAlignment(Qt.AlignCenter)
            table.item(row, 2).setTextAlignment(Qt.AlignCenter)
        layout.addWidget(table)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        layout.addWidget(close_btn)        
        dlg.setFixedWidth(sum(COL_WIDTH_DKP) + WIN_PAD + SCROLLBAR_WIDTH)
        dlg.exec_()

    def show_loot_history(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Loot History")
        layout = QVBoxLayout(dlg)
        table = QTableWidget(0, 3, dlg)
        table.setHorizontalHeaderLabels(["Date", "Player", "Item (Price)"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(table.NoEditTriggers)
        table.setSelectionMode(table.NoSelection)
        
        # Set column widths
        for i, w in enumerate(COL_WIDTH_LOOT):
            table.setColumnWidth(i, w)
        SCROLLBAR_WIDTH = app.style().pixelMetric(QApplication.style().PM_ScrollBarExtent)
        table.setFixedWidth(sum(COL_WIDTH_LOOT) + SCROLLBAR_WIDTH)
        table.setMinimumHeight(300)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Flatten and sort all loot by date desc
        loot_rows = []
        for name, p in self.players.items():
            for l in p.get("loot", []):
                date = l.get("date", "")[:10]  # yyyy-mm-dd
                item = l.get("name", "") or l.get("item", "")
                cost = l.get("cost", 0)
                loot_rows.append((date, name, f"{item} ({cost} DKP)"))
        loot_rows.sort(reverse=True)  # Newest first

        for date, name, desc in loot_rows:
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(date))
            table.setItem(row, 1, QTableWidgetItem(name))
            table.setItem(row, 2, QTableWidgetItem(desc))
            table.item(row, 0).setTextAlignment(Qt.AlignCenter)
            table.item(row, 1).setTextAlignment(Qt.AlignCenter)
        layout.addWidget(table)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        layout.addWidget(close_btn)     
        dlg.setFixedWidth(sum(COL_WIDTH_LOOT) + WIN_PAD + SCROLLBAR_WIDTH)
        dlg.exec_()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DKPManager()
    window.show()
    sys.exit(app.exec_())
