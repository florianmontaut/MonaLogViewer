
# controller/graph_controller.py

from typing import OrderedDict
import numpy as np

from PyQt6 import QtCore,QtGui,QtWidgets
import pyqtgraph as pg
import pyqtgraph.parametertree as ptree
from model.base_objects import SignalObject,DerivedSignalObject
from ressources import custom_graph_functions,custom_types,custom_items,custom_menu

from controller.graph_context_menu_controller import GraphContextMenu
from controller.graph_option_controller import GraphTreeController

class RelativeTimeAxis(pg.DateAxisItem):
    #? faire de même pour l'axe Y ?
    def tickStrings(self, values, scale, spacing):
        labels = []
        for v in values:
            if spacing < 1:
                labels.append(f"{v*1000:.0f} ms")
            elif spacing < 60:
                labels.append(f"{v:.2f} s")
            elif spacing < 3600:
                labels.append(f"{v/60:.1f} min")
            elif spacing < 3600*24:
                labels.append(f"{v/3600:.1f} h")
            else:
                labels.append(f"{v/(3600*24):.1f} day")
        return labels


class GraphController(QtCore.QObject):
    """
    Gère l'affichage PyQtGraph :
    - création courbes
    - update visibilité
    - update style
    - update pipeline (sig.y recalcule automatiquement)
    """

    curve_selected          = QtCore.pyqtSignal(custom_items.SelectionContext)
    reference_requested     = QtCore.pyqtSignal(SignalObject)
    cursor_moved_X          = QtCore.pyqtSignal(float)
    menu_actions_triggered  = QtCore.pyqtSignal(    custom_types.ActionModifier,
                                                    custom_types.qSignalType,
                                                    object)

    def __init__(self, graph_widget : pg.GraphicsLayoutWidget, graphtree : ptree ,**opts):
        super().__init__()
        self.graph = graph_widget
        self.graph_tree = graphtree
        self.time_axis = RelativeTimeAxis(orientation='bottom')
        self.curves = {}  # SignalObject → PlotDataItem
        # Espacement vertical entre signaux visibles
        self.digital_signals = OrderedDict()
        self.analog_signals = OrderedDict()

        self.signal_spacing = 1.5
        self.nb_signaux = 0
        self.old_highlight              = None
        self.old_highlight_width        = 1
        self.reference_sig              = None
        self.macro_recording            = False
        self.vcursor                    = None
        self.xp_axis                    = None
        self.yp_axis                    = None
        self._mouse_pos                 = 0
        self.visible_signal_positions   = {}
        # Stockage des TextItem affichant les valeurs logiques
        self.value_text_items = {}
        
        # options par défaut de l'objet, le premier init est réalisé
        # par le menu_controller
        self.opts = {

        "X_title"              : "Temps",
        "X_unit"               : "s",
        "X_major_t"            : 100,
        "X_minor_t"            : 20,
        "X_grid"               : True,
        "Y_title"              : "Temperature",
        "Y_unit"               : "°C",
        "Y_major_t"            : 10,
        "Y_minor_t"            : 2,
        "Y_grid"               : True,
        "update_selected"      : True,
        "downsample"           : True,
        "downsample_ratio"     : 10,
        "downsample_type"      : "peak",
        "background_color"     :"#FFFFFF",
        "dark_mode"            : False
        }


        if opts:
            self.updateOptions(**opts)
        self._init_graph()
        self._init_graph_menu()
        self._init_cursor()

    @property
    def mouse_pos(self):
        return self._mouse_pos #x = float(mouse_point.x())

    #! à revoir, en l'état si le fichier .JSON n'est pas conforme, ça peut planter le graph_ctrl
    #! peut-être faire une validation plus poussée dans le menu_controller avant d'appeler updateOptions
    def updateOptions(self,opts=None):
        if opts is not None:
            self.opts.update(opts)

        if self.opts["downsample"]:
            self.analog_plot.setDownsampling(mode=self.opts["downsample_type"],
                                            ds=self.opts["downsample_ratio"])

        if self.xp_axis is None:
            self.xp_axis = self.analog_plot.getAxis('bottom')

        self.xp_axis.setLabel(text = self.opts["X_title"], units = self.opts["X_unit"])
        xticks = [self.opts["X_major_t"], self.opts["X_minor_t"]]
        self.xp_axis.setTickSpacing(xticks[0],xticks[1])

        if self.yp_axis is None:
            self.yp_axis = self.analog_plot.getAxis('left')
        #! à reprendre
        '''
        self.yp_axis.setLabel(text=self.opts["Y_title"], units = self.opts["Y_unit"])
        yticks = [self.opts["Y_major_t"],self.opts["Y_minor_t"]]
        self.yp_axis.setTickSpacing(yticks[0], yticks[1])'''
        self.graph.setBackground(self.opts["background_color"])
        #self.analog_plot.showGrid(x = self.opts["X_grid"], y = self.opts["Y_grid"],alpha = 0.4)
        self.graph_tree_ctrl.update_settings(opts)


    def _init_graph(self):

        self._init_digital_plot()
        self._init_analog_plot()
        self.analog_plot.setXLink(self.digital_plot)
        self.vb_digital = self.digital_plot.vb
        self.vb_analog = self.analog_plot.vb
        self.graph.ci.layout.setRowStretchFactor(0, 2)
        self.graph.ci.layout.setRowStretchFactor(1, 3)
        self.vb_digital.autoRange()
        self.vb_analog.autoRange()
        self.vb_analog.setLimits(xMin = -0.81, xMax = 0.11)
        self.vb_digital.setLimits(xMin = -0.81, xMax = 0.11)
        self.vb_digital.sigRangeChanged.connect(self.update_value_text_positions)

    ############# méthodes contrôlant le graphe des entrées/sorties logiques ######################
    def _init_digital_plot(self,row = 0, col = 0):
        
        self.digital_plot = self.graph.addPlot(row=row, col=0)
        self.digital_plot.setLabel("left", "Signaux logiques")
        self.digital_plot.showGrid(x=True, y=False)
        self.digital_plot.setMouseEnabled(x = True, y = False)
        self.digital_plot_in_layout = True

    def update_digital_y_range(self, visible_indices):
        """
        Met à jour les graduations Y selon les signaux visibles uniquement.
        """

        y_ticks = []
        for display_index, signal_index in enumerate(visible_indices): #!  passage en sig
            y = display_index * self.signal_spacing + 0.5
            y_ticks.append((y, f"Signal {signal_index}"))
        self.digital_plot.getAxis("left").setTicks([y_ticks])
        self.digital_plot.getAxis("left").setStyle(tickLength=0)
        self.digital_plot.setMouseEnabled(y=False)

        #Ajuste la plage verticale du graphe selon le nombre de signaux visibles.
        nb_visible_signals=len(visible_indices)
        if nb_visible_signals == 0:
            self.digital_plot.setYRange(-0.5, 1.0)
        else:
            y_min = -0.5
            y_max = nb_visible_signals * self.signal_spacing
            self.digital_plot.setYRange(y_min, y_max)

    def get_visible_signal_indices(self):
        """
        Retourne la liste des indices réels des signaux actuellement cochés.
        """
        visible_indices = []
        for sig,index in self.digital_signals.items():
            if sig.visible:
                    visible_indices.append(index)

        return visible_indices


    def update_plots_layout(self, has_visible_digital_signals):
        """_summary_

        Args:
            has_visible_digital_signals (bool): _description_
        """

        if has_visible_digital_signals:
            # Case: at least one digital signal visible
            if not self.digital_plot_in_layout:
                # We remove the analog plot temporarily to reconstruct the layout
                self.graph.ci.removeItem(self.analog_plot)

                # Insert the digital plot at the top (row0)
                self.graph.ci.addItem(self.digital_plot, row=0, col=0)

                # Insert the analog plot below (row1)
                self.graph.ci.addItem(self.analog_plot, row=1, col=0)
                self.digital_plot_in_layout = True
                self.analog_plot_row = 1
                # Adjust row stretch: digital gets 2, analog gets 3 (as in the initial setup)
                self.graph.ci.layout.setRowStretchFactor(0, 2)
                self.graph.ci.layout.setRowStretchFactor(1, 3)
                # Restore the X link (should be already set, but just in case)
                self.analog_plot.setXLink(self.digital_plot)
        else:
            # Case: no digital signal visible
            if self.digital_plot_in_layout:
                # Remove both plots
                self.graph.ci.removeItem(self.digital_plot)
                self.graph.ci.removeItem(self.analog_plot)
                # Insert only the analog plot at the top (row0)
                self.graph.ci.addItem(self.analog_plot, row=0, col=0)
                self.digital_plot_in_layout = False
                self.analog_plot_row = 0
                self.graph.ci.layout.setRowStretchFactor(0, 1)   # only one row gets stretch factor 1
                # Keep the X link? The analog plot is still linked to the digital plot (even if not in layout)
                self.analog_plot.setXLink(self.digital_plot)

    def align_y_axes(self):
        """Align the Y axes of digital and analog plots by setting fixed width."""
        # Get the left axes
        digital_axis = self.digital_plot.getAxis('left')
        analog_axis = self.analog_plot.getAxis('left')

        # Calculate the width each axis needs for its label and ticks
        digital_width = digital_axis.width()
        analog_width = analog_axis.width()
        if digital_width < analog_width:
            max_width = analog_width
            digital_axis.setWidth(max_width)
        else:
            max_width = digital_width
            analog_axis.setWidth(max_width)


    
    def update_visible_curves_layout(self):
        """
        Recalcule automatiquement la disposition verticale des courbes visibles.

        Si une courbe est masquée, les courbes restantes sont compactées
        verticalement afin de ne pas laisser d'espace vide.
        """

        visible_indices = self.get_visible_signal_indices()
        self.visible_signal_positions.clear()

        # On masque tout d'abord toutes les courbes et tous les textes
        for sig,curve in self.curves.items():
            if sig.is_digital:
                curve.setVisible(False)
                self.value_text_items[sig].setVisible(False)

        # On replace uniquement les courbes visibles
        display_index=0
        for sig, signal_index in self.digital_signals.items():
            if signal_index in visible_indices:
                self.visible_signal_positions[sig] = display_index
                y_step = sig.y + display_index * self.signal_spacing
                self.curves[sig].setData(sig.x, y_step)
                display_index+=1
            self.curves[sig].setVisible(sig.visible)
            self.value_text_items[sig].setVisible(sig.visible)
            
        '''    
        for display_index, signal_index in enumerate(visible_indices):
            sig=digital_sig_list[signal_index]
            self.visible_signal_positions[signal_index] = display_index
            y_step = sig.y + display_index * self.signal_spacing

            self.curves[sig].setData(sig.x, y_step)
            self.curves[sig].setVisible(True)
            self.value_text_items[signal_index].setVisible(True)'''

        # Mise à jour de l'axe Y 
        self.update_digital_y_range(visible_indices)
        # Mise à jour des positions des valeurs logiques à gauche
        self.update_value_text_positions()

    def add_text_item(self,sig):
        """
        Crée un TextItem affichant les valeurs logiques à gauche du signal nouvellement créer.
        """

        text_item = pg.TextItem(
                                    text="-",
                                    color="#FFFFFF",
                                    anchor=(-0.5, 0.5)
                                )
        text_item.setFont(QtGui.QFont("Consolas", 16))
        self.digital_plot.addItem(text_item,ignoreBounds=True)
        self.value_text_items[sig] = text_item



    def update_value_text_positions(self):
        """
        Positionne les TextItem côté gauche du graphe,
        en suivant la disposition compacte des signaux visibles.
        """

        if not self.value_text_items:
            return
        
        view_range = self.vb_digital.viewRange()

        x_min = view_range[0][0]
        x_max = view_range[0][1]

        x_range = x_max - x_min
        x_offset = 0.01 * x_range

        # Position légèrement à gauche de la zone visible
        x_text = x_min - x_offset

        for sig, display_index in self.visible_signal_positions.items():
            y_text = display_index * self.signal_spacing + 0.5
            self.value_text_items[sig].setPos(x_text, y_text)
            
            
    ############# méthodes contrôlant le graphe des entrées/sorties logiques #####################   
    
    
    
    def _init_analog_plot(self, row = 1, col = 0):
        
        self.analog_plot = self.graph.addPlot(row=row, col=0)
        #self.analog_plot.setTitle("Signal analogique")
        #self.analog_plot.setLabel("bottom", "Échantillons")
        #self.analog_plot.setLabel("left", "Amplitude", units="V")
        if self.opts["downsample"]:
            self.analog_plot.setDownsampling(mode=self.opts["downsample_type"],
                                            ds=self.opts["downsample_ratio"])
            self.xp_axis = self.analog_plot.getAxis('bottom')
        if self.yp_axis is None:
            self.yp_axis = self.analog_plot.getAxis('left')
        self.yp_axis.setLabel(text=self.opts["Y_title"], units = self.opts["Y_unit"])
        yticks = [self.opts["Y_major_t"],self.opts["Y_minor_t"]]
        #self.yp_axis.setTickSpacing(yticks[0], yticks[1])
        self.yp_axis.enableAutoSIPrefix(False)
        self.analog_plot.setMouseEnabled(x = True, y = True)
        self.graph.setBackground(self.opts["background_color"])
        self.analog_plot.showGrid(x = self.opts["X_grid"], y = self.opts["Y_grid"],alpha = 0.4)
        self.analog_plot.showGrid(x=True, y=True)


    def update_vbox(self):
        self.vb_analog.autoRange()
        self.vb_digital.autoRange()
        
    # ----------------------------------------------------
    def add_signal_curve(self, sig: SignalObject|DerivedSignalObject):
        
        if sig not in self.curves.keys():
            curve = pg.PlotDataItem(sig.x, sig.y, pen=sig.pen)
            curve.setCurveClickable(True)
            curve.sigClicked.connect(self._on_curve_clicked)
            curve.setVisible(sig.visible) 
            self.curves[sig] = curve
            if sig.is_digital:
                self.nb_signaux+=1
                self.digital_plot.addItem(curve)
                self.add_text_item(sig)
                self.digital_signals[sig] = [n for n,signal in enumerate(sig.file.signals.values()) if signal==sig][0]
                self.update_visible_curves_layout()
            else:
                self.analog_plot.addItem(curve)
                self.analog_signals[sig]=len(self.analog_signals)
            
        
        self.align_y_axes()
        
    def _signal_from_curve(self, curve):
        for sig, c in self.curves.items():
            if c is curve:
                return sig
        return None

    def _on_curve_clicked(self,curve,event):
        sig = self._signal_from_curve(curve)
        self.highlight(sig)
        #print(f'signal: {sig.display_name}')
        if isinstance(sig, DerivedSignalObject):
            ctx = custom_items.SelectionContext(
                                    role=custom_items.itemType.DERIVED,
                                    signal=sig.parent_signal,
                                    derived_index=sig.parent_signal.derived_signals.index(sig),
                                    item=None,  # pas de TreeItem ici
                                )

        elif isinstance(sig, SignalObject):
            ctx = custom_items.SelectionContext(
                                    role=custom_items.itemType.RAW,
                                    signal=sig,
                                    item=None,
                                )
        else:
            #print(f'failed: {sig} / {type(sig)}')
            return  # sécurité
        """try:
            print(  "Graph_controller ligne 193: _on_curve_clicked => méthode appelée en cliquant sur une courbe: \n"+
                f'Signal: {ctx.signal.display_name}, role: {ctx.role}, filter index: {ctx.filter_index}'+
                f', Analysis index: {ctx.analysis_index}, derived index: {ctx.derived_index}\n')
        except:
            print('failed : échec d\'impression de données du CTX (Graph_controller)\n')"""
        self.curve_selected.emit(ctx)

    # ----------------------------------------------------
    def update_signal(self, sig):
        """Redessine la courbe après pipeline update."""
        if sig not in self.curves:
            return
        if sig.is_digital:
            self.update_visible_curves_layout()
        else:
            curve = self.curves[sig]
            curve.setData(sig.x, sig.y)
            curve.setPen(sig.pen)
            self.check_signal_visibiliy(sig,curve)
            
        self.align_y_axes()
        self.update_vbox()
    
    def check_signal_visibiliy(self,sig,curve = None):
        if sig not in self.curves:
            return
        if curve is None:
            curve = self.curves[sig]
        curve.setVisible(sig.visible)
        if sig.is_digital:
            self.update_visible_curves_layout()

    def freeze_updates(self, freeze: bool):
        self.graph.setUpdatesEnabled(not freeze)
        self.vb_digital.enableAutoRange(False)
        self.vb_analog.enableAutoRange(False)
        if not freeze:
            self.update_vbox()
            self.vb_digital.enableAutoRange(True)
            self.vb_analog.enableAutoRange(True)
            self.vb_digital.autoRange()
            self.vb_analog.autoRange()

    def select_graph_from_context(self,ctx:custom_items.SelectionContext):

        self.highlight(ctx.signal)

    def highlight(self, sig):
        """Met en surbrillance le signal sélectionné."""
        if sig not in self.curves.keys():
            return
        curve = self.curves[sig]
        self._update_cursor_color(curve)
        self.on_selection_changed(sig)

        if self.old_highlight != sig:
            # Highlight the new signal: double its current width (which should match sig.pen.width() if not previously highlighted)
            double_width = int(curve.opts['pen'].width() * 2)
            custom_graph_functions.updateCurve(curve, width=double_width, z_val=10)

            # Deselect the old signal
            if self.old_highlight is not None:
                old_curve = self.curves[self.old_highlight]
                current_width = old_curve.opts['pen'].width()
                expected_doubled_width = 2 * self.old_highlight_width

                if current_width == expected_doubled_width:
                    # The width was doubled and not changed by the user; revert to original
                    custom_graph_functions.updateCurve(old_curve, width=self.old_highlight_width)
                else:
                    # The width was changed by the user (e.g., via parameter tree); keep the new width but reset highlight properties
                    # Assuming custom_graph_functions.updateCurve can update z_val without changing width if width is not provided
                    custom_graph_functions.updateCurve(old_curve, z_val=0)  # Replace 0 with the default z-value if known

            # Update tracking variables
            self.old_highlight = sig
            self.old_highlight_width = sig.pen.width()  # Store the original width for the new highlight

    def remove_signal_curve(self, signal):
        curve = self.curves.pop(signal, None)
        if curve is not None:
            #!prévoir la gestion des tracés logiques
            self.analog_plot.removeItem(curve)
            curve.setParentItem(None)
            curve.deleteLater()
            #self.analog_plot.removeItem(curve) #crash intempestif lors des undo/redo

    def _init_cursor(self):

        self.graph_tree_ctrl = GraphTreeController(self.analog_plot,self.graph_tree,**self.opts)
        self.proxy = pg.SignalProxy(self.analog_plot.scene().sigMouseMoved,rateLimit = 50,
                                    slot = self._on_mouse_moved)


    def _update_cursor_color(self,curve):

        self.graph_tree_ctrl.mouseCursor.setCurve(curve)
        


    def _setup_mouse_guard(self):

        self._mouse_active = False
        self.analog_plot.scene().sigMouseMoved.connect(self._on_mouse_moved)
        self.analog_plot.scene().sigMouseClicked.connect(self._on_scene_mouse_clicked)


    def _on_scene_mouse_clicked(self, ev):
        pos = ev.scenePos()

        if self.vb.sceneBoundingRect().contains(pos):
            # clic dans le graphe
            if ev.button() == QtCore.Qt.MouseButton.LeftButton:
                self._mouse_active = True
                ev.accept()
                return
            elif ev.button() == QtCore.Qt.MouseButton.RightButton:
                self._mouse_active = False
                ev.accept()
                return
        else:
            # clic hors graphe
            self._mouse_active = False

    def _on_mouse_moved(self, ev):
        # Garde 2: souris sur le viewbox ?
        pos = ev[0]
        mousePoint = None 
        if  self.vb_digital.sceneBoundingRect().contains(pos):
            mousePoint = self.vb_digital.mapSceneToView(pos)
        if self.vb_analog.sceneBoundingRect().contains(pos) :
            mousePoint = self.vb_analog.mapSceneToView(pos)
        if mousePoint is None:
            return
        
        x_view = float(mousePoint.x())
        self.cursor_moved_X.emit(x_view)
        self.update_value_text_items_from_mouse(x_view)

    #MAJ de la position du curseur grâce à la position de la souris
    def _update_cursor(self, x: float, y: float | None):

        if x is None:
            return
        else:
            self.graph_tree_ctrl.mouseCursor.mouseUpdate(x,y,)
            #print(f'pos: {x}/{y}')
            '''
            if self.visible_signal_positions:
                file = self.digital_signals[0]
                #! ne peut pas fonctionné en l'état
                digital_values=file.get_Y_from_X_index(x)
                for signal_index,display_index in self.visible_signal_positions.items():
                    text_item = self.value_text_items[display_index]
                    value = int(digital_values[signal_index])
                    
                    text_item.setText(str(value))
                    if value == 1:
                        text_item.setColor("#00FF66")
                    else:
                        text_item.setColor("#FF5555")'''



    def update_value_text_items_from_mouse(self, x_view):
        """
        Met à jour les éléments TextItem pour les signaux numériques en fonction de la position actuelle de la souris.
        Convertit la coordonnée X de la souris en indice d'échantillon pour chaque signal et affiche la valeur Y arrondie.
        """
        for sig, text_item in self.value_text_items.items():
            # Ne mettre à jour que si l'élément TextItem est visible (pour éviter les travaux inutiles)
            if not text_item.isVisible():
                continue

            # Gérer le cas où le signal n'a pas de données
            if len(sig.x) == 0:
                text_item.setText("-")
                text_item.setColor("#FFFFFF")
                continue

            # Trouver l'indice dans sig.x le plus proche de x_view
            # On suppose que sig.x est trié (ce qui devrait être le cas pour les données temporelles)
            idx = np.searchsorted(sig.x, x_view, side='left')
            if idx == 0:
                i = 0
            elif idx == len(sig.x):
                i = len(sig.x) - 1
            else:
                # Comparer la distance à gauche et à droite
                if x_view - sig.x[idx-1] <= sig.x[idx] - x_view:
                    i = idx-1
                else:
                    i = idx

            # Obtenir la valeur Y calculée (après pipeline) à cet indice
            y_val = sig.y[i]
            # Arrondir à l'entier le plus proche et limiter à 0 ou 1
            int_val = round(y_val)
            if int_val < 0:
                int_val = 0
            elif int_val > 1:
                int_val = 1
            else:
                int_val = int(int_val)

            # Mettre à jour le texte et la couleur de l'élément TextItem
            text_item.setText(str(int_val))
            if int_val == 1:
                text_item.setColor("#00FF66")  # Vert pour logique haut
            else:
                text_item.setColor("#FF5555")  # Rouge pour logique bas




    def _init_graph_menu(self):
        """
        méthode alembiqué mais permet de voir la technique de passage d'information
        via les slots et non pas via signals
        """
        self.menu = GraphContextMenu(
                                        self.analog_plot,
                                        action_callback=self.actions_forwarding
                                    )
        self.on_selection_changed(None)

    def actions_forwarding(self, action_type, macro_name=None):
        """
        Route l'action demandée vers la bonne méthode métier
        """
        if action_type == custom_types.qSignalType.TEXT:
            self.graph_tree_ctrl.addText()
        else:
            self.menu_actions_triggered.emit(   custom_types.ActionModifier.ADD_ACTION,
                                                action_type,
                                                macro_name)

    def on_selection_changed(self,sig:SignalObject=None):

        # actuellement seul un signal d'un même DataFrame peut servir de référence.
        if sig is not None:
            states = custom_menu.SelectionState(
                                        has_selection = True,
                                        has_reference = (self.reference_sig is not None and
                                                        not sig.is_reference) ,
                                        is_recording= self.macro_recording
                                        )
        else:
            states = custom_menu.SelectionState(
                                        has_selection = False,
                                        has_reference = False,
                                        is_recording= self.macro_recording
                                        )

        self.menu.update_enabled_states(states)


    def set_reference_signal(self, sig : SignalObject):

        self.reference_sig = sig