

import sys
import numpy as np

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

import pyqtgraph as pg


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Affichage de signaux logiques")
        self.resize(1200, 600)

        # Nombre de signaux et nombre d'échantillons
        self.nb_signaux = 5
        self.nb_points = 50

        # Génération d'un tableau de 5 signaux booléens aléatoires
        # Shape : (5, nb_points)
        self.signaux = np.random.randint(
            low=0,
            high=2,
            size=(self.nb_signaux, self.nb_points),
            dtype=np.uint8
        )

        # Espacement vertical entre signaux visibles
        self.signal_spacing = 1.5

        # Stockage des courbes pyqtgraph
        self.signal_curves = []

        # Stockage des TextItem affichant les valeurs logiques
        self.value_text_items = []

        # Stockage des items de l'arborescence
        self.tree_items = []

        # Dictionnaire : signal_index réel -> position d'affichage visible
        self.visible_signal_positions = {}

        # Widget central principal
        self.central_widget = QWidget()
        self.main_layout = QHBoxLayout(self.central_widget)

        # Widget graphique principal pyqtgraph
        self.graphics_layout = pg.GraphicsLayoutWidget()


        # PlotItem logique existant
        self.plot_item = self.graphics_layout.addPlot(row=0, col=0)

        # PlotItem analogique ajouté dessous
        self.analog_plot_item = self.graphics_layout.addPlot(row=1, col=0)

        # Liaison de l'axe X du plot analogique avec le plot logique
        self.analog_plot_item.setXLink(self.plot_item)

        # États de présence dans le layout
        self.logic_plot_in_layout = True
        self.analog_plot_row = 1

        # Optionnel : le graphe logique prend plus de hauteur que l'analogique
        self.graphics_layout.ci.layout.setRowStretchFactor(0, 2)
        self.graphics_layout.ci.layout.setRowStretchFactor(1, 3)


        # Arborescence de contrôle
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabel("Signaux")
        self.tree_widget.setMinimumWidth(180)

        # Ajout dans l'IHM
        self.main_layout.addWidget(self.graphics_layout, stretch=5)
        self.main_layout.addWidget(self.tree_widget, stretch=1)

        self.setCentralWidget(self.central_widget)

        # Configuration
        self.configure_plot()
        self.create_signal_curves()
        
        self.configure_analog_plot()
        self.display_analog_signal()

        self.configure_value_text_items()
        self.configure_tree_widget()
        self.configure_cursor_reader()

        
        
        # Disposition initiale
        self.update_visible_curves_layout()

    def configure_plot(self):
        self.plot_item.setTitle("Signaux logiques aléatoires")
        #self.plot_item.setLabel("bottom", "Échantillons")
        self.plot_item.setLabel("left", "Signaux logiques")
        self.plot_item.showGrid(x=True, y=False)
        self.plot_item.setXRange(0, self.nb_points)
        self.plot_item.setYRange(-0.5, self.nb_signaux * self.signal_spacing)

    def create_signal_curves(self):
        """
        Crée les courbes une seule fois.
        Leur position verticale sera ensuite recalculée dynamiquement
        par update_visible_curves_layout().
        """

        colors = [
            "#00FF22",
            "#16FF35",
            "#16FF35",
            "#16FF35",
            "#00FF32",
        ]

        for i in range(self.nb_signaux):
            pen = pg.mkPen(color=colors[i], width=2)

            curve = self.plot_item.plot(
                [],
                [],
                pen=pen,
                name=f"Signal {i}"
            )
            self.signal_curves.append(curve)

    def configure_tree_widget(self):
        """
        Crée une arborescence contenant une checkbox par signal.
        L'état de la checkbox pilote l'affichage de la courbe correspondante.
        """

        for i in range(self.nb_signaux):
            item = QTreeWidgetItem(self.tree_widget)
            item.setText(0, f"Signal {i}")
            item.setCheckState(0, Qt.CheckState.Checked)
            # On stocke l'indice réel du signal dans l'item
            item.setData(0, Qt.ItemDataRole.UserRole, i)

            self.tree_items.append(item)

        self.tree_widget.expandAll()

        self.tree_widget.itemChanged.connect(self.on_tree_item_changed)

    def on_tree_item_changed(self, item, column):
        """
        Callback appelé lorsque l'état d'une checkbox change.
        """

        if column != 0:
            return

        # À chaque changement, on recalcule toute la disposition verticale
        self.update_visible_curves_layout()

    def get_visible_signal_indices(self):
        """
        Retourne la liste des indices réels des signaux actuellement cochés.
        """

        visible_indices = []

        for item in self.tree_items:
            signal_index = item.data(0, Qt.ItemDataRole.UserRole)

            if item.checkState(0) == Qt.CheckState.Checked:
                visible_indices.append(signal_index)

        return visible_indices

    
    #* DEJA COPIE
    def configure_analog_plot(self):
        """
        Configure le PlotItem dédié aux signaux analogiques.
        L'axe X est lié à celui du PlotItem logique.
        """

        self.analog_plot_item.setTitle("Signal analogique")
        self.analog_plot_item.setLabel("bottom", "Échantillons")
        self.analog_plot_item.setLabel("left", "Amplitude", units="V")

        self.analog_plot_item.showGrid(x=True, y=True)

        # Même plage X que les signaux logiques
        self.analog_plot_item.setXRange(0, self.nb_points)

        self.analog_plot_item.setYRange(-1.2, 1.2)
    #* DEJA COPIE

    def display_analog_signal(self):
        """
        Affiche une sinusoïde 50 Hz sur une période,
        échantillonnée en 50 points comme les signaux logiques.
        """

        frequency = 50.0
        period = 1.0 / frequency

        # Même nombre de points que les signaux logiques
        x = np.arange(self.nb_points)

        # Temps physique associé à chaque échantillon
        # endpoint=False pour avoir exactement 50 échantillons sur une période
        t = np.linspace(
            0.0,
            period,
            self.nb_points,
            endpoint=False
        )

        amplitude = 1.0
        sinus = amplitude * np.sin(2.0 * np.pi * frequency * t)

        pen = pg.mkPen(color="#FFD700", width=2)

        self.analog_curve = self.analog_plot_item.plot(
            x,
            sinus,
            pen=pen,
            name="Sinus 50 Hz"
        )

    def build_step_signal(self, signal_index, display_index):
        """
        Construit les données X/Y en escalier pour un signal donné,
        en tenant compte de sa position verticale visible.
        """

        x = np.arange(self.nb_points)

        signal = self.signaux[signal_index]

        y = signal + display_index * self.signal_spacing

        # Affichage en escalier
        x_step = np.repeat(x, 2)[1:]
        x_step = np.append(x_step, x[-1] + 1)

        y_step = np.repeat(y, 2)

        return x_step, y_step

    def update_visible_curves_layout(self):
        """
        Recalcule automatiquement la disposition verticale des courbes visibles.

        Si une courbe est masquée, les courbes restantes sont compactées
        verticalement afin de ne pas laisser d'espace vide.
        """

        visible_indices = self.get_visible_signal_indices()
        self.update_plot_items_layout(has_visible_logic_signals=len(visible_indices) > 0)

        self.visible_signal_positions.clear()

        # On masque tout d'abord toutes les courbes et tous les textes
        for i in range(self.nb_signaux):
            self.signal_curves[i].setVisible(False)
            self.value_text_items[i].setVisible(False)
        if visible_indices:
        # On replace uniquement les courbes visibles
            for display_index, signal_index in enumerate(visible_indices):
                self.visible_signal_positions[signal_index] = display_index

                x_step, y_step = self.build_step_signal(
                                                        signal_index=signal_index,
                                                        display_index=display_index
                                                    )

                self.signal_curves[signal_index].setData(x_step, y_step)
                self.signal_curves[signal_index].setVisible(True)
                self.value_text_items[signal_index].setVisible(True)
        elif self.is_item_in_graphics_layout(self.plot_item):
            self.graphics_layout.removeItem(self.plot_item)
        

        # Mise à jour de l'axe Y
        self.update_y_axis_ticks(visible_indices)

        # Mise à jour des limites Y
        self.update_y_range(len(visible_indices))

        # Mise à jour des positions des valeurs logiques à gauche
        self.update_value_text_positions()




    def is_item_in_graphics_layout(self, item):
        """
        Vérifie si un item est actuellement présent dans le GraphicsLayout.
        """
        try:
            self.graphics_layout.ci.itemIndex(item)
            return True
        except ValueError:
            return False





    def update_plot_items_layout(self, has_visible_logic_signals):
        """
        Met à jour dynamiquement la présence du PlotItem logique dans le layout.

        - Si aucun signal logique n'est visible :
            le plot logique est retiré du GraphicsLayoutWidget
            et le plot analogique remonte en row=0.

        - Si au moins un signal logique est visible :
            le plot logique est réinséré en row=0
            et le plot analogique est placé en row=1.
        """

        if has_visible_logic_signals:
            # Cas : au moins un signal logique visible
            if not self.logic_plot_in_layout:
                # On retire temporairement le plot analogique pour reconstruire proprement
                self.graphics_layout.ci.removeItem(self.analog_plot_item)

                # On réinsère le plot logique en haut
                self.graphics_layout.ci.addItem(
                                                self.plot_item,
                                                row=0,
                                                col=0
                                            )

                # On remet le plot analogique dessous
                self.graphics_layout.ci.addItem(
                                                    self.analog_plot_item,
                                                    row=1,
                                                    col=0
                                                )
                self.logic_plot_in_layout = True
                self.analog_plot_row = 1
                self.graphics_layout.ci.layout.setRowStretchFactor(0, 3)
                self.graphics_layout.ci.layout.setRowStretchFactor(1, 1)
                # On restaure explicitement le lien X
                self.analog_plot_item.setXLink(self.plot_item)
        else:
            # Cas : aucun signal logique visible

            if self.logic_plot_in_layout:
                # On retire les deux plots du layout pour éviter les lignes vides
                self.graphics_layout.ci.removeItem(self.plot_item)
                self.graphics_layout.ci.removeItem(self.analog_plot_item)
                # On réinsère uniquement le plot analogique en haut
                self.graphics_layout.ci.addItem(
                                                    self.analog_plot_item,
                                                    row=0,
                                                    col=0
                                                )
                self.logic_plot_in_layout = False
                self.analog_plot_row = 0
                self.graphics_layout.ci.layout.setRowStretchFactor(0, 1)

                # Le lien X peut rester actif même si le plot logique est retiré du layout
                self.analog_plot_item.setXLink(self.plot_item)

    #* DEJA COPIE
    def update_y_axis_ticks(self, visible_indices):
        """
        Met à jour les graduations Y selon les signaux visibles uniquement.
        """

        y_ticks = []

        if not visible_indices:
            self.plot_item.getAxis("left").setTicks([[]])
            return


        for display_index, signal_index in enumerate(visible_indices):
            y = display_index * self.signal_spacing + 0.5
            y_ticks.append((y, f"Signal {signal_index}"))

        self.plot_item.getAxis("left").setTicks([y_ticks])
        self.plot_item.getAxis("left").setStyle(tickLength=0)
        self.plot_item.setMouseEnabled(y=False)
    #* DEJA COPIE
    
    def update_y_range(self, nb_visible_signals):
        """
        Ajuste la plage verticale du graphe selon le nombre de signaux visibles.
        """

        if nb_visible_signals == 0:
            self.plot_item.setYRange(-0.5, 1.0)
        else:
            y_min = -0.5
            y_max = nb_visible_signals * self.signal_spacing
            self.plot_item.setYRange(y_min, y_max)
    #* DEJA COPIE
    #? infinite line en pointillé dans le graphe de signaux numériques ?#
    def configure_cursor_reader(self):
        """
        Configure la liaison entre la position X du curseur
        et la lecture des valeurs des signaux.
        """

        self.cursor_line = pg.InfiniteLine(
            angle=90,
            movable=False,
            pen=pg.mkPen(
                color="#FFFFFF",
                width=1,
                style=Qt.PenStyle.DashLine
            )
        )

        self.plot_item.addItem(self.cursor_line)

        self.mouse_proxy = pg.SignalProxy(
            self.plot_item.scene().sigMouseMoved,
            rateLimit=60,
            slot=self.on_mouse_moved
        )
    #? infinite line en pointillé dans le graphe de signaux numériques ?#
    
    #* DEJA COPIE
    def configure_value_text_items(self):
        """
        Crée les TextItem affichant les valeurs logiques à gauche des signaux.
        """

        for i in range(self.nb_signaux):
            text_item = pg.TextItem(
                text="-",
                color="#FFFFFF",
                anchor=(-0.5, 0.5)
            )

            text_item.setFont(QFont("Consolas", 16))

            self.plot_item.addItem(
                text_item,
                ignoreBounds=True
            )

            self.value_text_items.append(text_item)

        self.plot_item.vb.sigRangeChanged.connect(
            lambda: self.update_value_text_positions()
        )
    #* DEJA COPIE

    #* DEJA COPIE
    def update_value_text_positions(self):
        """
        Positionne les TextItem côté gauche du graphe,
        en suivant la disposition compacte des signaux visibles.
        """

        view_range = self.plot_item.vb.viewRange()

        x_min = view_range[0][0]
        x_max = view_range[0][1]

        x_range = x_max - x_min
        x_offset = 0.01 * x_range

        # Position légèrement à gauche de la zone visible
        x_text = x_min - x_offset

        for signal_index, display_index in self.visible_signal_positions.items():
            y_text = display_index * self.signal_spacing + 0.5
            self.value_text_items[signal_index].setPos(x_text, y_text)
    #* DEJA COPIE
    
    #! récupérer le code notamment np.clip
    def on_mouse_moved(self, event):
        """
        Callback appelé lorsque la souris se déplace dans la scène.
        """

        #sécu 
        if not self.logic_plot_in_layout:
            return

        scene_pos = event[0]
        

        if self.plot_item.sceneBoundingRect().contains(scene_pos):
            mouse_point = self.plot_item.vb.mapSceneToView(scene_pos)

            x_float = mouse_point.x()
            x_index = int(np.floor(x_float))
            x_index = np.clip(x_index, 0, self.nb_points - 1)
            self.cursor_line.setPos(x_index)
            visible_indices = self.get_visible_signal_indices()
            title_values = []
            for signal_index in visible_indices:
                value = int(self.signaux[signal_index, x_index])
                self.value_text_items[signal_index].setText(str(value))
                if value == 1:
                    self.value_text_items[signal_index].setColor("#00FF66")
                else:
                    self.value_text_items[signal_index].setColor("#FF5555")
                title_values.append(f"S{signal_index}={value}")
            values_text = " | ".join(title_values)
            self.plot_item.setTitle(
                f"Index X = {x_index}   |   {values_text}"
            )

            self.update_value_text_positions()


def main():
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
