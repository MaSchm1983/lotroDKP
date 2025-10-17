import sys, json, os, requests
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QDialog, QLineEdit, QLabel, QComboBox, QMessageBox, QSpinBox, QFileDialog, QListWidget, QListWidgetItem, QCheckBox
)
from PyQt5.QtGui import QIcon, QPixmap, QColor, QBrush
from PyQt5.QtCore import Qt, QSize, QByteArray, QBuffer

# --- Utility: download and cache icons ---
ICON_CACHE = {}
COL_WIDTH = [40, 50, 100, 60, 300]
COL_WIDTH_DKP = [110, 120, 120]     # Player | Awarded | Spent (adjust as you like)
COL_WIDTH_LOOT = [90, 110, 210]     # Date | Player | Item (Price)
WIN_PAD = 28 # 14px left + 14px right, for example
#SCROLLBAR_WIDTH = 20 


def get_scrollbar_width():
    app = QApplication.instance()
    if app is None:
        # In practice your app exists by the time UI is shown, but be defensive.
        # Fallback to a sane default width if needed.
        return 16
    return app.style().pixelMetric(QApplication.style().PM_ScrollBarExtent)

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
        try:
            resp = requests.get(path_or_url, timeout=8)
            if not resp.ok or not resp.content:
                return QIcon()
            pix = QPixmap()
            if not pix.loadFromData(resp.content):
                return QIcon()
            icon = QIcon(pix)
            ICON_CACHE[path_or_url] = icon
            return icon
        except Exception:
            return QIcon()
    else:
        if os.path.exists(path_or_url):
            icon = QIcon(path_or_url)
            ICON_CACHE[path_or_url] = icon
            return icon
        return QIcon()

def color_for_status(status: str):
    s = (status or "").strip().lower()
    if s == "done":
        # soft grey-blue with transparency
        return QColor(100, 130, 195, 60)   # RGBA (alpha 0-255)
    if s == "open":
        # lime-green-ish with transparency
        return QColor(50, 205, 50, 60)
    if s == "twink":
        # Windows-ish blue with transparency
        return QColor(0, 100, 225, 60)
    return None


# --- Main App ---
class DKPManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Die Ritters von Rohan DKP Helegrod")
        # app = QApplication.instance() or QApplication([])
        SCROLLBAR_WIDTH = get_scrollbar_width()
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
        self.remove_btn = QPushButton("Remove Player")
        #self.open_btn = QPushButton("Open DKP File")
        #self.save_btn = QPushButton("Save DKP File")
        btnrow.addWidget(self.add_btn)
        btnrow.addWidget(self.award_btn)
        btnrow.addWidget(self.spend_btn)
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
        
        # add refresh button to reaload data from .json, otherwise the code use only internal memory until changes are made
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setToolTip("Reload DKP data from file")
        refresh_btn.setFixedWidth(100)
        filter_row.addWidget(refresh_btn)
        self.refresh_btn = refresh_btn  # in case you want to use it elsewhere
        refresh_btn.clicked.connect(self.do_refresh)
        #refresh_btn.clicked.connect(lambda: self.load_dkp(self.dkp_file_path or resource_path("lotro_dkp_backup.json")))
        # refresh_btn.clicked.connect(lambda: self.load_dkp(self.dkp_file_path))
        
        
        # Table
        
        SCROLLBAR_WIDTH = get_scrollbar_width()
        self.table = QTableWidget(0, len(COL_WIDTH))        
        for col, width in enumerate(COL_WIDTH):
            self.table.setColumnWidth(col, width)
        self.table.setHorizontalHeaderLabels(["#", "Class", "Name", "DKP", "Loot"])
 
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
        self.table.cellClicked.connect(self.on_table_cell_clicked)
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
    
    def do_refresh(self):
        self.players = {}
        self.dkp_history = []
        self.dkp_file_path = resource_path("lotro_dkp_backup.json")
        self.load_dkp(self.dkp_file_path)

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
        # --- FILTER logic at the start ---
        selected_class = self.filter_combo.currentText() if hasattr(self, 'filter_combo') else "--all--"
        players = sorted(self.players.items(), key=lambda t: (-t[1].get("dkp", 0), t[0]))
        if selected_class != "--all--":
            players = [(name, p) for name, p in players if p.get("class") == selected_class]

        self.table.setRowCount(len(players))

        for row, (name, p) in enumerate(players):
            # --- Column 0: rank number ---
            num_item = QTableWidgetItem(str(row + 1))
            num_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, num_item)

            # --- Column 1: class icon (local path) ---
            icon_path = self.class_icons.get(p.get("class", ""), "")
            citem = QTableWidgetItem()
            citem.setIcon(get_icon(icon_path))
            citem.setText("")
            citem.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 1, citem)

            # --- Column 2: name + tooltip for twinks ---
            pname_item = QTableWidgetItem(name)
            twinks = p.get("Twinks", [])
            if twinks:
                tt_lines = []
                for idx, t in enumerate(twinks, 1):
                    tclass = t.get("class", "")
                    tname = t.get("name", "")
                    ticon_path = self.class_icons.get(tclass, "")
                    if ticon_path and os.path.exists(ticon_path):
                        ticon = QPixmap(ticon_path).scaled(15, 15, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        ba = QByteArray()
                        buffer = QBuffer(ba)
                        buffer.open(QBuffer.WriteOnly)
                        ticon.save(buffer, "PNG")
                        b64 = ba.toBase64().data().decode()
                        icon_html = f' <img src="data:image/png;base64,{b64}" width="15" height="15" style="vertical-align:middle; margin-bottom:+5px;">'
                    else:
                        icon_html = f" [{tclass}]"
                    tt_lines.append(f"{idx}. {tname}{icon_html}")
                tooltip_html = "<b>Twinks:</b><br>" + "<br>".join(tt_lines)
                pname_item.setToolTip(tooltip_html)
            self.table.setItem(row, 2, pname_item)

            # --- Column 3: DKP ---
            dkp_item = QTableWidgetItem(str(p.get("dkp", 0)))
            dkp_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, dkp_item)

            # --- Column 4: Loot icons (URLs!) ---
            loot = p.get("loot", [])[-10:]
            loot_widget = QWidget()
            loot_widget.setAttribute(Qt.WA_StyledBackground, True)  # allow bg color via stylesheet
            loot_hbox = QHBoxLayout(loot_widget)
            loot_hbox.setContentsMargins(8, 0, 0, 0)
            loot_hbox.setSpacing(2)

            for l in loot:
                li = QLabel()
                li.setAttribute(Qt.WA_TranslucentBackground)    # be explicit: no own background
                li.setStyleSheet("background: transparent;")     # (some styles still need this)
                icon_url = l.get("icon", "")
                if icon_url:
                    li.setPixmap(get_icon(icon_url).pixmap(24, 24))
                else:
                    li.setText("?")
                date_str = l.get("date", "")[:10]
                tip = f"{l.get('name','') or l.get('item','')}\n{l.get('cost','')} DKP\n{date_str}"
                li.setToolTip(tip)
                loot_hbox.addWidget(li)

            loot_widget.setLayout(loot_hbox)
            self.table.setCellWidget(row, 4, loot_widget)

            # --- Clear any previous background styling for the whole row ---
            for c in range(self.table.columnCount()):
                it = self.table.item(row, c)
                if it:
                    it.setBackground(QBrush())
            loot_w = self.table.cellWidget(row, 4)
            if loot_w:
                loot_w.setStyleSheet("")

            # --- Apply row background color once, based on status ---
            status = p.get("status", "")
            qcol = color_for_status(status)
            if qcol:
                brush = QBrush(qcol)
                for c in range(self.table.columnCount()):
                    it = self.table.item(row, c)
                    if it:
                        it.setBackground(brush)
                if loot_w:
                    loot_w.setStyleSheet(
                        f"background-color: rgba({qcol.red()},{qcol.green()},{qcol.blue()},{qcol.alpha()});"
                        "border-radius: 4px; padding-left: 4px;"
                    )
        self.table.setAlternatingRowColors(False)  # avoid fighting the tint
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
                pdata = {"name": pname, "class": pcl, "dkp": 0,"status": "open", "loot": []}
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

    

    def show_award_dkp(self):
        if not self.players:
            QMessageBox.information(self, "Info", "No players.")
            return
        
        dlg = QDialog(self)
        dlg.setWindowTitle("Award DKP")
        v = QVBoxLayout(dlg)
        
        # Players list
        label = QLabel("Players:")
        v.addWidget(label)
        playerlist = QListWidget()
        playerlist.setSelectionMode(QListWidget.MultiSelection)
        for pname in sorted(self.players):
            item = QListWidgetItem(pname)
            playerlist.addItem(item)
        v.addWidget(playerlist)
        
        total_players = playerlist.count()
        sel_counter = QLabel(f"Selected: 0 / {total_players}")
        v.addWidget(sel_counter)
        
        def update_sel_counter():
            sel_count = len(playerlist.selectedItems())
            sel_counter.setText(f"Selected: {sel_count} / {total_players}")
            
        playerlist.itemSelectionChanged.connect(update_sel_counter)
        update_sel_counter
                
        # DKP amount
        dkp_label = QLabel("Add DKP:")
        v.addWidget(dkp_label)
        dkp_input = QSpinBox()
        dkp_input.setMinimum(1)
        dkp_input.setMaximum(9999)
        dkp_input.setValue(100)
        v.addWidget(dkp_input)
        
        # action
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
        dkp_input.setMinimum(0)
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

    def on_table_cell_clicked(self, row, col):
        # Only respond to name column (col 2)
        if col != 2:
            return
        item = self.table.item(row, col)
        if not item:
            return
        pname = item.text()
        if pname not in self.players:
            return
        self.show_player_loot_popup(pname)
        
    def show_player_loot_popup(self, pname):
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Details: {pname}")
        layout = QVBoxLayout(dlg)

        # Table for Loot History
        loot_table = QTableWidget(0, 5, dlg)
        loot_table.setHorizontalHeaderLabels(["Date", "Name", "Class", "Item", "DKP Spent"])
        loot_table.verticalHeader().setVisible(False)
        loot_table.setEditTriggers(loot_table.NoEditTriggers)
        loot_table.setSelectionMode(loot_table.NoSelection)
        loot_table.setFixedWidth(520)   # Wider for more info
        loot_table.setMinimumHeight(300)
        loot_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        loot_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Helper: add loot rows (main or twink)
        def add_loot_rows(owner_name, owner_class, loot_list):
            for l in loot_list:
                date = l.get("date", "")[:10]
                item_name = l.get("name", "") or l.get("item", "")
                cost = l.get("cost", 0)
                icon_url = l.get("icon", "")
                row = loot_table.rowCount()
                loot_table.insertRow(row)
                loot_table.setItem(row, 0, QTableWidgetItem(date))
                loot_table.setItem(row, 1, QTableWidgetItem(owner_name))
                loot_table.setItem(row, 2, QTableWidgetItem(owner_class))
                
                # --- Icon only, with tooltip ---
                icon_label = QLabel()
                icon_label.setAlignment(Qt.AlignCenter)
                if icon_url:
                    icon = get_icon(icon_url)
                    icon_label.setPixmap(icon.pixmap(25, 25))
                else:
                    icon_label.setText("?")
                icon_label.setToolTip(f"{item_name}")
                loot_table.setCellWidget(row, 3, icon_label)

                loot_table.setItem(row, 4, QTableWidgetItem(str(cost)))

                # Center align for all but icon
                for col in [0, 1, 2, 4]:
                    loot_table.item(row, col).setTextAlignment(Qt.AlignCenter)

        # ---- Collate all loot (main + twinks) ----
        pdata = self.players[pname]
        total_loot_rows = 0
        add_loot_rows(pname, pdata.get("class", ""), pdata.get("loot", []))
        total_loot_rows += len(pdata.get("loot", []))
        for twink in pdata.get("Twinks", []):
            tname = twink.get("name")
            tclass = twink.get("class", "")
            tloot = []
            if tname in self.players:
                tloot = self.players[tname].get("loot", [])
            add_loot_rows(tname, tclass, tloot)
            total_loot_rows += len(tloot)

        layout.addWidget(QLabel(f"<b>Loot History (last {total_loot_rows} items):</b>"))
        layout.addWidget(loot_table)

        # --- DKP Awards section (main + twinks) ---
        # DKP awards are not per-date in your structure, just totals unless you store history.
        # Let's show current DKP, spent DKP, and total awarded (main + twinks)
        def get_award_spent_loot(p):
            current = p.get("dkp", 0)
            spent = sum(l.get("cost", 0) for l in p.get("loot", []))
            awarded = current + spent
            return awarded, spent

        awarded_main, spent_main = get_award_spent_loot(pdata)
        dkp_award_info = f"<b>DKP (main):</b> Awarded: {awarded_main} | Spent: {spent_main} | Current: {pdata.get('dkp', 0)}"
        # Twinks:
        twink_awards = []
        for twink in pdata.get("Twinks", []):
            tname = twink.get("name")
            if tname in self.players:
                tp = self.players[tname]
                award, spent = get_award_spent_loot(tp)
                twink_awards.append(f"{tname}: Awarded: {award} | Spent: {spent} | Current: {tp.get('dkp', 0)}")
        if twink_awards:
            dkp_award_info += "<br><b>Twinks:</b><br> " + "<br> ".join(twink_awards)
        layout.addWidget(QLabel(dkp_award_info))

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        layout.addWidget(close_btn)
        dlg.setFixedWidth(520)  # Even wider window
        dlg.exec_()


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
        SCROLLBAR_WIDTH = get_scrollbar_width()
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
        SCROLLBAR_WIDTH = get_scrollbar_width()
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
