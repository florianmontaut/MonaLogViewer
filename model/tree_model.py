
# model/tree_model.py

import numpy as np
import pathlib

from PyQt6.QtCore import Qt, QModelIndex, QAbstractItemModel
from PyQt6.QtGui import QColor,QBrush,QFont,QIcon
from model.tree_item import TreeItem
from model.base_objects import FileObject, SignalObject,Workspace,SignalGroupObject,Folder
from model.filters.base_filter import FilterNode
from model.analysis.base_analysis import AnalysisNode
from PyQt6.QtCore import QObject, pyqtSignal

from model.base_objects import SignalObject
from ressources.custom_items import itemType,ModelChangeEvent,ActionModifier

PATH=pathlib.Path(__file__).parent.parent


    

class PipelineTreeModel(QAbstractItemModel):

    node_event          = pyqtSignal(object)
    visibility_changed  = pyqtSignal(object)

    def __init__(self, workspace: Workspace, parent=None):
        super().__init__(parent)

        self.workspace = workspace

        self.icon_file              = QIcon(str(PATH)+"/ressources/icons/file.svg")
        self.icon_signal_raw        = QIcon(str(PATH)+"/ressources/icons/signal_raw.svg")
        self.icon_signal_modified   = QIcon(str(PATH)+"/ressources/icons/signal_modified.svg")
        self.icon_filter            = QIcon(str(PATH)+"/ressources/icons/filter.svg")
        self.icon_signal_reference  = QIcon(str(PATH)+"/ressources/icons/signal_reference.svg")
        self.root_item = TreeItem('root')

        #curseur Global
        self.cursor_x = None  # position du curseur (abscisse)

        # ✅ index par fichier
        self.cursor_Y_values_by_file = {}  # FileObject → list[float]
        self.signal_index_map = {}
        self._items_by_object_id = {}
        # build signals
        self.build_tree()

    def build_tree(self):
        self.beginResetModel()
        #self.root_item = TreeItem("Workspace")

        self.files_root = TreeItem(Folder("Files"), parent=self.root_item)
        self.groups_root = TreeItem(Folder("Groups"), parent=self.root_item)

        self.root_item.add_child(self.files_root)
        self.root_item.add_child(self.groups_root)

        for file_obj in self.workspace.files.values():
            file_item = TreeItem(file_obj, parent=self.files_root)
            self.files_root.add_child(file_item)

            for sig in file_obj.signals.values():
                sig_item = TreeItem(sig, parent=file_item)
                file_item.add_child(sig_item)

                for filt in sig.pipeline.values():
                    sig_item.add_child(TreeItem(filt, parent=sig_item))

                for analysis in sig.analyses.values():
                    sig_item.add_child(TreeItem(analysis, parent=sig_item))

        for group in self.workspace.groups.values():
            group_item = TreeItem(group, parent=self.groups_root)
            self.groups_root.add_child(group_item)

            for ref in group.references.values():
                sig = self.workspace.resolve_signal(ref.file_id, ref.signal_id)

                if sig is not None:
                    ref_item = TreeItem(sig, parent=group_item)
                    group_item.add_child(ref_item)
        
        self.endResetModel()
        if self.cursor_x is not None:
            self.updateCursorVal(self.cursor_x)

    """def _build_tree(self):
        self.root_item.children.clear()

        for file_obj in self.workspace.files:
            self.add_file_subtree(file_obj)"""


    # ----------------- Build file subtree -----------------

    def add_file_subtree(self, file_obj: FileObject):
        parent_index = self.index_from_item(self.files_root)
        row = self.files_root.child_count()

        file_item = TreeItem(file_obj, parent=self.files_root)

        for sig in file_obj.signals.values():
            self._add_signal_subtree_silent(sig, file_item)

        self.beginInsertRows(parent_index, row, row)
        self.files_root.insert_child(row, file_item)
        self.endInsertRows()

        if self.cursor_x is not None:
            self.updateCursorVal(self.cursor_x)

    # ----------------- Build signal subtree -----------------
    def _add_signal_subtree_silent(self, sig: SignalObject, file_item: TreeItem):
        """
        Ajoute un signal et ses enfants dans l'arbre sans notification Qt.

        À utiliser uniquement lorsque le parent est lui-même en cours d'insertion,
        par exemple dans add_file_subtree().
        """

        sig_item = TreeItem(sig, parent=file_item)
        file_item.add_child(sig_item)

        for filt in sig.pipeline.values():
            filt_item = TreeItem(filt, parent=sig_item)
            sig_item.add_child(filt_item)

        for analysis in sig.analyses.values():
            analysis_item = TreeItem(analysis, parent=sig_item)
            sig_item.add_child(analysis_item)
            
    def add_signal_subtree(self, sig: SignalObject, parent:TreeItem):
        """
        Ajoute dynamiquement un SignalObject sous un FileObject déjà présent.
        À utiliser hors insertion du fichier parent.
        """
        sig_item = TreeItem(sig, parent = parent)
        parent.add_child(sig_item)

        # ✅ on mémorise l'index
        index = self.createIndex(len(parent.children)-1,0,sig_item)
        self.signal_index_map[sig] = index


        for node in sig.pipeline.values():
            filter_item = TreeItem( node,
                                    parent = sig_item,
                                    )
            sig_item.add_child(filter_item)

        # --- Analyses ---
        for analysis in sig.analyses:
            analysis_item = TreeItem(   analysis,
                                        parent = sig_item,
                                    )
            sig_item.add_child(analysis_item)
            # Ajouter les signaux DÉRIVÉS de cette analyse
            for derived_sig in sig.derived_signals:
                if (hasattr(derived_sig, 'metadata') and
                    derived_sig.metadata.get('analysis_id') == analysis.id):
                    derived_item = TreeItem(derived_sig,
                                            parent = analysis_item,
                                            )
                    analysis_item.add_child(derived_item)

    def remove_file_subtree(self, file_obj):
        """
        Supprime un FileObject du modèle Qt proprement.
        """
        # trouver l'index du FileObject
        root_item = self.root_item
        row = None

        for i, child in enumerate(root_item.children):
            if child.obj is file_obj:
                row = i
                break

        if row is None:
            return  # sécurité

        parent_index = QModelIndex()
        self.beginRemoveRows(parent_index, row, row)
        root_item.children.pop(row)
        self.endRemoveRows()

    def _emit_children_check_state_changed(self, parent_item: TreeItem):
        if parent_item.child_count() == 0:
            return

        parent_index = self.index_from_item(parent_item)

        top_left = self.index(0, 0, parent_index)
        bottom_right = self.index(parent_item.child_count() - 1, 0, parent_index)

        if top_left.isValid() and bottom_right.isValid():
            self.dataChanged.emit(
                top_left,
                bottom_right,
                [Qt.ItemDataRole.CheckStateRole]
            )
            
    def _emit_check_state_refresh_for_item(self, item: TreeItem):
        idx = self.index_from_item(item)

        if idx.isValid():
            self.dataChanged.emit(
                idx,
                idx,
                [Qt.ItemDataRole.CheckStateRole]
            )

        self._emit_children_check_state_changed(item)
        
    def _emit_subtree_changed(self, item):
        """
        Notifie Qt que l'état checkable de tout le sous-arbre peut avoir changé.
        Simple et robuste.
        """
        first = self.index_from_item(item)

        if first.isValid():
            self.dataChanged.emit(first,first,[Qt.ItemDataRole.CheckStateRole])

        for child in item.children:
            self._emit_subtree_changed(child)
            
    def emit_node_event(self, action, item : TreeItem):
        ctx = item.to_selection_context()
        if ctx is None:
            return
        self.node_event.emit(ModelChangeEvent(action=action,context=ctx))

    def _register_item(self, item):
        obj_id = getattr(item.obj, "id", None)

        if obj_id is None:
            return

        self._items_by_object_id.setdefault(obj_id, []).append(item)
    # ---------------------- Model API ----------------------
    def index(self, row, column, parent):
        """Retourne l'index Qt pour une position donnée."""
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        parent_item = self.root_item if not parent.isValid() else parent.internalPointer()
        child = parent_item.child(row)

        if child:
            return self.createIndex(row, column, child)
        return QModelIndex()

    def parent(self, index = None,item=None):
        """Retourne l'index parent d'un index donné."""

        if item is None:
            if index is None :
                return QModelIndex()
            if not index.isValid():
                return QModelIndex()
            item = index.internalPointer()
        parent_item = item.parent_item

        if parent_item == self.root_item or parent_item is None:
            return QModelIndex()
        return self.createIndex(parent_item.row(), 0, parent_item)

    # méthode inutile car le header est caché
    def headerData(self, section, orientation, role):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if section == 0:
                return "Signal"
            elif section == 1:
                return "Value @ Cursor"
        return None
    
    def index_from_item(self, item: TreeItem):
        if item is None or item.parent_item is None:
            return QModelIndex()
        return self.createIndex(item.row(), 0, item)
    
    def rowCount(self, parent):
        if not parent.isValid():
            return self.root_item.child_count()
        return parent.internalPointer().child_count()

    def columnCount(self, parent):
        # 0 = Nom + icône + Visible (checkbox)
        # 1 = Valeur au curseur
        return 2
    
    # ---------------------- Checkbox state ----------------------
    def _emit_self_check_changed(self, item):
        idx = self.index_from_item(item)
        if idx.isValid():
            self.dataChanged.emit(idx,idx,[Qt.ItemDataRole.CheckStateRole])
    
    def _emit_subtree_check_changed(self, item):
        self._emit_self_check_changed(item)
        for child in item.children:
            self._emit_subtree_check_changed(child)
    
    def _emit_ancestors_check_changed(self, item):
        parent = item.parent_item
        while parent is not None:
            idx = self.index_from_item(parent)
            if idx.isValid():
                self.dataChanged.emit(idx,idx,[Qt.ItemDataRole.CheckStateRole])
            parent = parent.parent_item
    def _emit_global_check_refresh(self):
        root_index = QModelIndex()
        self.dataChanged.emit(
                                self.index(0, 0, QModelIndex()),
                                self.index(self.rowCount(root_index) - 1, 0, QModelIndex()),
                                [Qt.ItemDataRole.CheckStateRole]
                            )
    def _check_state_from_bools(self, values: list[bool]):
        if not values:
            return Qt.CheckState.Unchecked
        if all(values):
            return Qt.CheckState.Checked
        if not any(values):
            return Qt.CheckState.Unchecked
        return Qt.CheckState.PartiallyChecked
    
    def _check_state_for_object(self, obj):
        if obj.item_type == itemType.RAW:
            return ( Qt.CheckState.Checked if obj.visible else Qt.CheckState.Unchecked)
        if obj.item_type == itemType.FILE:
            states = [sig.visible for sig in obj.signals.values()]
            return self._check_state_from_bools(states)
        if obj.item_type == itemType.GROUP:
            states = []
            for ref in obj.references.values():
                sig = self.workspace.resolve_signal(ref.file_id, ref.signal_id)
                if sig is not None:
                    states.append(sig.visible)
            return self._check_state_from_bools(states)
        return None
    
    def _is_checkable_object(self, obj):
        return isinstance(obj,(     FileObject,
                                    SignalGroupObject,
                                    SignalObject,)
                            )
    def _set_file_visibility(self, file_obj: FileObject, visible: bool):
        impacted = []

        for sig in file_obj.signals.values():
            if sig.visible != visible:
                sig.visible = visible
                impacted.append(sig)

        return impacted
    
    def _set_group_visibility(self, group: SignalGroupObject, visible: bool):
        impacted = []

        for ref in group.references.values():
            sig = self.workspace.resolve_signal(ref.file_id, ref.signal_id)

            if sig is None:
                continue

            if sig.visible != visible:
                sig.visible = visible
                impacted.append(sig)

        return impacted

    def _emit_check_state_updates(self, item, impacted_signals):
        # parent + enfants directs
        self._emit_check_state_refresh_for_item(item)
        # autres occurrences éventuelles des mêmes signaux
        for sig in impacted_signals:
            self._emit_items_for_signal_changed(sig)
            
    def _emit_items_for_signal_changed(self, signal):
        items = self._items_by_object_id.get(signal.id, [])

        for item in items:
            idx = self.index_from_item(item)

            if idx.isValid():
                self.dataChanged.emit(
                    idx,
                    idx,
                    [Qt.ItemDataRole.CheckStateRole]
                )

            self._emit_ancestors_check_state_changed(item)
# ---------------------- Gestion du text dynamique dans l'arborescence ----------------------
    def _signal_display_text(self, sig):
        if sig.item_type != itemType.RAW:
            return ""
        file=sig.file
        val=self.cursor_Y_values_by_file[file][sig.name]
        if isinstance(val, (float, np.floating)):
            return f"{val:.3g}{sig.unit}"
        else:
            return "-"

    def _display_text(self, obj):
        obj_type = obj.item_type
        if obj_type == itemType.FOLDER:
            return obj.name

        if obj_type == itemType.FILE:
            return getattr(obj, "name", None) or getattr(obj, "address", "File")

        if obj_type == itemType.GROUP:
            return obj.name

        if obj_type == itemType.RAW:
            return obj.name
        return getattr(obj, "display_name", str(obj))

# ---------------------- Gestion de la police dynamique dans l'arborescence ----------------------
    def _font_for_object(self,obj):
        if  obj.is_selected:
            font = QFont("Times", 10)
            font.setBold(True)
            return font
        return QFont()
    
# ---------------------- Gestion de la couleur du texte dans l'arborescence ----------------------
    def _foreground_for_object(self,obj):
        if obj.item_type== itemType.RAW and getattr(obj,'is_reference'):
            return QBrush(QColor("#D32F2F"))  # rouge profond
        else:
            return QBrush(QColor("#000000"))  # noir profond
        
# ---------------------- Gestion de la couleur des cases dans l'arborescence ----------------------
    def _background_for_object(self,obj):
        
        if obj.item_type == itemType.RAW:
                        # Couleur de fond = couleur du signal
                        color = QColor(obj.pen.color())
                        # léger alpha pour rester lisible
                        color.setAlpha(150)
                        return QBrush(color)
                    
# ---------------------- Gestion des icônes dynamique dans l'arborescence ----------------------

    def _icon_for_object(self,obj):
        obj_type = obj.item_type
        # FileObject
        if obj_type == itemType.FILE:
            return self.icon_file

        # SignalObject
        if obj_type == itemType.RAW:

            if obj.is_reference:
                return self.icon_signal_reference
            elif obj.is_modified:
                return self.icon_signal_modified
            else:
                return self.icon_signal_raw
        # FilterNode
        if obj_type == itemType.FILTER:
            return self.icon_filter

# ---------------------- Contrôle du TreeView  ----------------------

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        item = index.internalPointer()
        obj = item.obj
        col = index.column()
        
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return self._display_text(obj)
            elif col == 1:
                if self.cursor_x is None:
                    return "-"
                return self._signal_display_text(sig=item.obj)
            
        if role == Qt.ItemDataRole.CheckStateRole and (self._is_checkable_object(obj)
                                                        and col == 0):
            return self._check_state_for_object(obj)
        if role == Qt.ItemDataRole.ForegroundRole:
            return self._foreground_for_object(obj)
        if role == Qt.ItemDataRole.BackgroundRole:
            return self._background_for_object(obj)
        if role == Qt.ItemDataRole.FontRole:
            return self._font_for_object(obj)
        if role == Qt.ItemDataRole.DecorationRole and col == 0:
            return self._icon_for_object(obj)
        return None
    

    # ---------------------- Checkbox handling ----------------------
    
    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if not index.isValid():
            return False

        if role != Qt.ItemDataRole.CheckStateRole:
            return False

        item : TreeItem = index.internalPointer()
        obj = item.obj
        obj_type = obj.item_type
        visible = value == 2 #2==Qt.CheckState.Checked
        impacted_signals = []
        if obj_type == itemType.FILE:
            impacted_signals = self._set_file_visibility(obj, visible)
        elif obj_type == itemType.GROUP:
            impacted_signals = self._set_group_visibility(obj, visible)
        elif obj_type in (itemType.RAW,itemType.FILTER,itemType.ANALYSE):
            if obj.visible !=visible:
                obj.visible = visible
                impacted_signals = [obj]
        else:
            return False

        self._emit_check_state_updates(item, impacted_signals)
        self.visibility_changed.emit(item.to_selection_context())

        return True

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        item = index.internalPointer()
        obj = item.obj
        flags = ( Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsSelectable)
        if self._is_checkable_object(obj):
            flags |= Qt.ItemFlag.ItemIsUserCheckable
        if isinstance(obj, (FileObject, SignalGroupObject)):
            flags |= Qt.ItemFlag.ItemIsAutoTristate
        return flags

    # ---------------------- Update pipeline (undo/redo) ----------------------

    def insert_node(self, sig: SignalObject, node, node_id: str):
        """Insère un node dans l'arbre."""
        signal_item = self.find_item(self.root_item, sig)
        if not signal_item:
            return
        row_index = sig.get_filter_index_by_id(node_id)
        if row_index is None:
            row_index = sig.get_analysis_index_by_id(node_id)
        parent_index = self.index_from_item( signal_item)
        node_item = TreeItem(node, parent = signal_item)

        self.beginInsertRows(parent_index, row_index, row_index)
        signal_item.children.insert(row_index, node_item)
        self.endInsertRows()

        self.emit_node_event(ActionModifier.ADD_ACTION, node_item)

    def remove_node(self, sig: SignalObject, node_id: str):
        signal_item = self.find_item(self.root_item, sig)
        if not signal_item:
            return
        item = self.find_item_by_object_id(node_id, signal_item)

        if item is None:
            return
        row_index = self.index_from_item(item).row()
        
        parent_index =  self.index_from_item(signal_item)
        self.beginRemoveRows(parent_index, row_index, row_index)
        signal_item.children.pop(row_index)
        self.endRemoveRows()
        self.emit_node_event(ActionModifier.REMOVE_ACTION,item)
        

    def update_node(self, signal, node_id):

        signal_item = self.find_signal_item(signal)

        if signal_item is None:
            return
        item = self.find_item_by_object_id(node_id, signal_item)

        if item is None:
            return
        row_index = self.index_from_item(item).row()
        if row_index.isValid():
            self.dataChanged.emit(row_index, row_index)
        self.emit_node_event(ActionModifier.MODIFY_ACTION, item)

    # ---------------------- Search ----------------------

    def find_item(self, item: TreeItem, target_obj):

        if item.obj is target_obj:
            return item
        for child in item.children:
            found = self.find_item(child, target_obj)
            if found:
                return found
        return None

    def find_item_by_object_id(self, obj_id, root_item=None):
        if obj_id is None:
            return None

        if root_item is None:
            root_item = self.root_item

        if getattr(root_item.obj, "id", None) == obj_id:
            return root_item

        for child in root_item.children:
            found = self.find_item_by_object_id(obj_id, child)
            if found is not None:
                return found

        return None

    def find_signal_item(self, signal):
        return self.find_item_by_object_id(signal.id)

    def find_filter_item(self, signal, filter_id):
        signal_item = self.find_signal_item(signal)

        if signal_item is None:
            return None

        return self.find_item_by_object_id(filter_id, signal_item)

    def find_analysis_item(self, signal, analysis_id):
        signal_item = self.find_signal_item(signal)

        if signal_item is None:
            return None

        return self.find_item_by_object_id(analysis_id, signal_item)

    # ---------------------- MAJ des valeurs des signaux selon la position du curseur ----------------------

    def updateCursorVal(self,x):

        #MAJ de la colonne value / on peut envisager une version où la colonne serait  déplaçable
        self.cursor_x=x

        for file in self.workspace.files.values():
            xs = list(file.signals.values())[0].x
            idx = np.argmin(np.abs(xs - np.ones(len(xs))*x))
            self.cursor_Y_values_by_file[file]=file.get_Y_from_X_index(idx)

        tl = self.index(0, 1, QModelIndex())
        br = self.index(self.rowCount(QModelIndex()) - 1, 1, QModelIndex())
        self.dataChanged.emit(tl, br, [Qt.ItemDataRole.DisplayRole])
        
        
    

    # ---------------------- Méthode gérant les opérations sur les nodes groupes ----------------------
    def insert_group(self, group):
        parent_item = self.groups_root

        row = parent_item.child_count()

        self.beginInsertRows(
            self.index_from_item(parent_item),
            row,
            row
        )

        group_item = TreeItem(group, parent=parent_item)
        parent_item.append_child(group_item)

        self.endInsertRows()

        ctx = group_item.to_selection_context()

        if ctx is not None and hasattr(self, "node_event"):
            self.node_event.emit(
                ModelChangeEvent(
                    action=ActionModifier.ADD_ACTION,
                    context=ctx
                )
            )
    
    def insert_signal_reference(self, group, signal):
        group_item = self.find_item_by_object_id(group.id)

        if group_item is None:
            return

        # éviter doublon visuel
        ref_key = f"{getattr(signal.parent_file, 'id', None)}:{signal.id}"

        for child in group_item.children:
            child_sig = child.obj
            child_file = getattr(child_sig, "parent_file", None)
            child_key = f"{getattr(child_file, 'id', None)}:{getattr(child_sig, 'id', None)}"

            if child_key == ref_key:
                return

        row = group_item.child_count()
        self.beginInsertRows(
                                self.index_from_item(group_item),
                                row,
                                row
                            )

        sig_item = TreeItem(signal, parent=group_item)
        group_item.append_child(sig_item)

        self.endInsertRows()

        ctx = sig_item.to_selection_context()

        if ctx is not None and hasattr(self, "node_event"):
            self.node_event.emit(
                ModelChangeEvent(
                    action=ActionModifier.ADD_ACTION,
                    context=ctx
                )
            )
    
    def remove_signal_reference(self, group, signal):
        group_item = self.find_item_by_object_id(group.id)

        if group_item is None:
            return

        target_row = None

        for row, child in enumerate(group_item.children):
            if getattr(child.obj, "id", None) == signal.id:
                target_row = row
                break

        if target_row is None:
            return

        self.beginRemoveRows(
            self.index_from_item(group_item),
            target_row,
            target_row
        )

        group_item.remove_child(target_row)

        self.endRemoveRows()

        ctx = group_item.to_selection_context()

        if ctx is not None and hasattr(self, "node_event"):
            self.node_event.emit(
                ModelChangeEvent(
                    action=ActionModifier.REMOVE_ACTION,
                    context=ctx
                )
            )