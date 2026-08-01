from PyQt6 import QtCore,QtGui,QtWidgets
from ressources.custom_types import qSignalType
from ressources.custom_items import itemType
from dataclasses import dataclass


@dataclass
class SelectionState:
    
    # --- TreeView management ---
    has_selection: bool
    
    # --- Differential management ---
    has_reference: bool
    
    # --- Macro management ---
    is_recording: bool
    
    # --- TreeItem/ Group management ---
    is_signal: bool             = False
    is_file: bool               = False
    is_group: bool              = False
    is_signal_in_group: bool    = False
    has_groups: bool            = False

@dataclass(frozen=True)
class ActionSpec:
    label: str
    enabled_if: callable


class BaseContextMenu(QtCore.QObject):

    ACTION_SPECS = {
                    qSignalType.FILTER : ActionSpec(
                                        label="Filter selection",
                                        enabled_if= lambda s: s.has_selection and
                                                            s.is_signal
                                        ),
                    qSignalType.REF : ActionSpec(
                                        label="Set as temperature ref",
                                        enabled_if= lambda s:   s.has_selection
                                        ),
                    qSignalType.DIFF : ActionSpec(
                                        label="Get temperature rise",
                                        enabled_if= lambda s:   (s.has_selection
                                                                and s.has_reference)
                                        ),
                    qSignalType.OFFSET_X : ActionSpec(
                                        label="Add an X offset",
                                        enabled_if= lambda s: s.has_selection
                                        ),
                    qSignalType.OFFSET : ActionSpec(
                                        label="Add an Y offset",
                                        enabled_if= lambda s: s.has_selection
                                        ),
                    qSignalType.MODEL : ActionSpec(
                                        label="Get thermal model",
                                        enabled_if= lambda s: s.has_selection
                                        ),
                    qSignalType.ISOLATE : ActionSpec(
                                        label="Isolate selection",
                                        enabled_if= lambda s: s.has_selection
                                        ),
                    qSignalType.DEL : ActionSpec(
                                        label="Delete selection",
                                        enabled_if= lambda s: s.has_selection
                                        ),
                    
                    # --------------------------------------------------
                    # Macro actions
                    # --------------------------------------------------
                    qSignalType.START : ActionSpec(
                                        label="Start macro recording",
                                        enabled_if= lambda s:   (s.has_selection
                                                                and not s.is_recording)
                                        ),
                    qSignalType.STOP : ActionSpec(
                                        label="Stop macro recording",
                                        enabled_if= lambda s:   (s.has_selection
                                                                and s.is_recording)
                                        ),
                    qSignalType.MACRO : ActionSpec(
                                        label="Apply macro",
                                        enabled_if= lambda s: s.has_selection
                                        ),
                    
                    # --------------------------------------------------
                    # Group actions
                    # --------------------------------------------------
                    qSignalType.CREATE_GROUP : ActionSpec(
                                        label="Create group",
                                        enabled_if= lambda s: s.has_selection
                                        ),
                    qSignalType.ADD_TO_GROUP : ActionSpec(
                                        label="Add to group",
                                        enabled_if= lambda s: s.has_selection
                                        ),
                    qSignalType.REMOVE_FROM_GROUP : ActionSpec(
                                        label="Remove from group",
                                        enabled_if= lambda s: s.has_selection
                                        ),
                    # --------------------------------------------------
                    # Graph actions
                    # --------------------------------------------------
                    qSignalType.TEXT : ActionSpec(
                                        label="Add text",
                                        enabled_if= lambda s: s.has_selection
                                        ),
                    }


    def __init__(self, menu: QtWidgets.QMenu, action_callback):
        super().__init__()
        self.menu = menu
        self._action_callback = action_callback
        self._actions = {}
        # sécurité ownership Qt/Python pour les sous-menus (évite que les objets créer soit
        # supprimées par le garbecollector)
        self._submenus = []
        self._build_menu()



    # --------------------------------------------------
    # Payload dynamique
    # --------------------------------------------------


    def _get_payload(self):
        """
        Surchargé par les menus spécialisés.
        Exemple TreeContextMenu : retourne le SelectionContext courant.
        """
        return None

    def _on_action_triggered(self, action_type):
        payload = self._get_payload()
        self._action_callback(action_type, payload)



    def _add_action(self, action_type, payload=None):
        spec=self.ACTION_SPECS[action_type]
        
        act = QtGui.QAction(spec.label, self.menu)
        act.setData(action_type)
        
        act.triggered.connect(
                                lambda _, e=action_type, p=payload:
                                            self._action_callback(e, p)
                            )
        self._actions[action_type] = act
        return act

    def _add_submenu(   self,
                        title: str,
                        item:QtGui.QAction|QtWidgets.QMenu=None
                    )-> QtWidgets.QMenu:
        
        if item is None:
            self.menu.addMenu(submenu)
        elif isinstance(item,QtGui.QAction):
            submenu = QtWidgets.QMenu(title, self.menu)
            self.menu.insertMenu(item,submenu)
        elif isinstance(item, QtWidgets.QMenu):
            submenu = item.addMenu(title)
        else:
            raise TypeError(
                    f"_add_submenu expected QAction, QMenu or None, got {type(item)}"
                    )
        # Garde une référence Python explicite.
        # Cela évite certains comportements pénibles avec les objets Qt imbriqués.
        if not hasattr(self, "_submenus"):
            self._submenus = []
        self._submenus.append(submenu)
        
        return submenu

    def update_enabled_states(self, selection_state:SelectionState):
        for action_type, action in self._actions.items():
            spec = self.ACTION_SPECS[action_type]
            enabled = spec.enabled_if(selection_state)
            action.setText(spec.label)
            action.setEnabled(enabled)


    def _build_menu(self):
        raise NotImplementedError

    # --------------------------------------------------
    # State computation
    # --------------------------------------------------

    def _build_selection_state(self, ctx):
        if ctx is None:
            return SelectionState()

        node = ctx.get_node() if hasattr(ctx, "get_node") else None
        return SelectionState(
                                has_selection=True,
                                # à connecter si tu as une ref thermique active dans MainController
                                has_reference=False,
                                # optionnel : setter depuis MainController si nécessaire
                                is_recording=False,
                                is_signal   =   ctx.role in (itemType.RAW,itemType.ANALYSE,itemType.FILTER),
                                is_file     =   ctx.role == itemType.FILE,
                                is_group    =   ctx.role == itemType.GROUP,
                                is_signal_in_group=(
                                                    ctx.signal is not None
                                                    and ctx.group is not None
                                                    ),
                                # optionnel : pourra être injecté depuis le controller
                                has_groups=True,
                                )


'''
class MacroContextMenuController(QtCore.QObject):

    macro_recording = QtCore.pyqtSignal(qSignalType)
    macro_request = QtCore.pyqtSignal(qSignalType,str)

    def __init__(   self,
                    menu: QtWidgets.QMenu,
                ):
        super().__init__()
        self.menu = menu
        self._build_menu()

    def _build_menu(self):
        self.macro_menu = self.menu.addMenu("Macro")

        self.start_action = QtGui.QAction("Start recording actions", self.menu)
        self.stop_action  = QtGui.QAction("Stop recording", self.menu)

        self.start_action.triggered.connect(lambda x=qSignalType.START:
                                            self.macro_recording.emit(x))
        self.stop_action.triggered.connect(lambda x=qSignalType.STOP:
                                            self.macro_recording.emit(x))
        self.macro_menu.addAction(self.start_action)
        self.macro_menu.addAction(self.stop_action)
        self.macro_menu.addSeparator()
        self.apply_menu = self.macro_menu.addMenu("Apply macro")

    def update_state(self,is_recording):
        self.start_action.setEnabled(not is_recording)
        self.stop_action.setEnabled(is_recording)

    def register_macro(self, macro):
        name=macro.name
        action = QtGui.QAction(name, self.menu)
        action.triggered.connect(lambda x=qSignalType.MACRO,y=name:
                                            self.macro_request.emit(x,y))
        self.apply_menu.addAction(action)'''
