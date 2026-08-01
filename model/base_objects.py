
# model/base_objects.py

from turtle import color

from PyQt6 import QtCore, QtGui
from collections import OrderedDict

import numpy as np
import pandas as pd
import json

from dataclasses import dataclass,field
from typing import NamedTuple, Optional

import pyqtgraph as pg
import pyqtgraph.parametertree as ptree


from ressources import custom_parameters,custom_struct_functions
from ressources.custom_items import itemType,FileStruct
from model.tree_item import TreeItem


import uuid



class FileObject:
    """
    Représente un fichier chargé (CSV, CAN, UDP...), contenant :

    - un DataFrame complet
    - tous les SignalObject (raw + calculés)
    """


    item_type = itemType.FILE
    PARAMETER_SCHEMA= {
                        'Event informations'    :{
                                            'type': 'group',
                                            'expanded':True,
                                            'visible':False,
                                            'children':{
                                                        'Converter number':{
                                                                        'type':'str',
                                                                        'default':None,
                                                                        "readonly": True,
                                                                        "key": "CVS_num"
                                                                    },
                                                        'Event id':{
                                                                        'type':'str',
                                                                        'default':None,
                                                                        "readonly": True,
                                                                        "key": "log_id"
                                                                    },
                                                        'Event type':{
                                                                        'type':'str',
                                                                        'default':None,
                                                                        "readonly": True,
                                                                        "key": "event_name"
                                                                    },
                                                        'Event occurences':{
                                                                        'type':'str',
                                                                        'default':None,
                                                                        "readonly": True,
                                                                        "key": "event_occurences"
                                                                    },
                                                        },
                                            
                        },
                        'File editor' :{
                                            'type': 'group',
                                            'expanded':True,
                                            'visible':False,
                                            'children':
                                                    {
                                                    'Time offset':{
                                                                        'type':'float',
                                                                        'default':0.0,
                                                                        'suffix': "s",
                                                                        "readonly": False,
                                                                        "key": "offset"
                                                                        },
                                                    'Truncate left':{
                                                                        'type':'float',
                                                                        'default':0.0,
                                                                        'limits':[0.0,None],
                                                                        "suffix": "s",
                                                                        "readonly": False,
                                                                        "key": "start_x"
                                                                        },
                                                    'Truncate right':{
                                                                        'type':'float',
                                                                        'default':0.0,
                                                                        'limits':[0.0,None],
                                                                        "suffix": "s",
                                                                        "readonly": False,
                                                                        "key": "stop_x"
                                                                        }
                                                    }
                                        }
                    }

    n_colors=20

    def __init__(self, fileData : FileStruct ):

        for key,val in fileData.__dict__.items():
            setattr(self,key,val)

        self.address        :   str
        self.sampling       :   float
        self.n_samples      :   int
        self.recordDate     :   str
        self.import_params  :   dict
        self.data           :   pd.DataFrame
        self.name           :   str
        self.file_type      :   str
        self.start_x        :   float
        self.stop_x         :   float
        self.offset         :   int
        self.id = uuid.uuid4().hex
        self.visible = True
        self.signals = OrderedDict()   # Liste de SignalObject
        self.is_selected = False
        self.opts_dict = custom_struct_functions.generate_opts_dict(self.PARAMETER_SCHEMA)
        self.colormap = pg.colormap.getFromMatplotlib('tab20')
        self.colors = self.colormap.getLookupTable(0,1,self.n_colors)
        #+ 4 styles de pinceaux, soit 4*n_colors combinaisons
        self.penStyle = [QtCore.Qt.PenStyle.SolidLine,
                        QtCore.Qt.PenStyle.DashLine,
                        QtCore.Qt.PenStyle.DotLine,
                        QtCore.Qt.PenStyle.DashDotLine]
        self.matis_color_scheme={   
                                    'GREY'              :   "#747474",
                                    'YELLOW'            :   "#FFFB00",
                                    'ORANGE'            :   "#FF7B00",
                                    'RED'               :   "#FF0000",
                                    'BLUE'              :   "#0026FF",
                                    'LIGHT_BLUE'        :   "#00C3FF",
                                    'LIGHT_PURPLE'      :   "#CA58FF",
                                    'LIGHT_RED'         :   "#F36767",
                                    'PURPLE'            :   "#860092",
                                    'WHITE'             :   "#FFFFFF",
                                    'BROWN'             :   "#724400",
                                    'LIGHT_BROWN'       :   "#B16207",
                                    'GREEN'             :   "#2B8801",
                                    'LIGHT_GREEN'       :   "#3ADF24",
                                    'LIGHT_ORANGE'      :   "#F08B49",
        }
        
    @property
    def signalsCount (self)-> int:
        return len(self.signals.values())

    def set_offset(self,time):
        if time is not None:
            if  time != self.offset:
                self.offset = time
                if isinstance(self.data.index, pd.MultiIndex):
                    #on retire l'index time existant
                    self.data = self.data.reset_index(level = 1,drop = True)
                #ajout d'une colonne Time / pas besoin de l'insérer en tête de la dataFrame
                #comme dans les versions précédentes
                self.data['Time'] = np.linspace(self.offset,
                                                self.offset+(self.n_samples-1)*self.sampling,
                                                self.n_samples)
                #on définit la nouvelle colonne time comme deuxième index
                self.data = self.data.set_index('Time',append = True)

    @property
    def display_name(self):
        """Le signal a-t-il subit une modification"""
        return self.name + (" *" if self.offset!=0 or self.start_x!=0 or self.stop_x!=0 else "")

    def get_params(self)-> dict:
        """Récupère l'ensemble des paramètres du signal sous forme de dictionnaire clé-valeur,
        à partir de la structure définie dans opts_dict."""

        return {key:getattr(self, key) for param_path,key in self.opts_dict.items()}

    def get_param(self,key):
        """Récupère la valeur d'un paramètre à partir de sa clé."""
        if hasattr(self,key):
            return getattr(self, key)
        else:
            return self.import_params.get(key)

    def set_params(self,newParams):
        """Met à jour les paramètres du signal à partir d'un groupe de paramètres."""
        '''_params = custom_struct_functions.extract_parameter_values(   self.PARAMETER_SCHEMA,
                                                                    newParams)'''

        for key, value in newParams.items():
            if key == "offset":
                self.set_offset(value)
            else:
                setattr(self, key, value)

    def set_visible(self, visible: bool):
        self.visible = visible

        for sig in self.signals.values():
            sig.visible = visible

    def get_channels_params(self,name):
        
        #channels_setting est une liste de dictionnaire
        channel_settings=self.get_param("channels_setting")
        
        for channel in channel_settings:
            
            if name ==  channel.get('name'):
                return  channel
            
        return  None


    def add_signal(self, name: str):
        """Ajoute un signal brut ou calculé."""
        
        settings = self.get_channels_params(name)
        if settings is None:
            pen=self.getDefaultPen()
            sig = SignalObject(self, name, pen)
        else:
            color = self.matis_color_scheme.get(settings['color'],None)
            if color is None:
                pen=self.getDefaultPen()
            elif settings['is_digital']:
                pen = pg.mkPen(color= "#16FF35")
            else:
                pen=pg.mkPen(color=color)
            sig = SignalObject(self, name, pen, is_digital= settings['is_digital'])
        
        
        self.signals[sig.id] = sig
        return sig

    def get_Y_from_X_index(self,index:int):
        """
        Méthode ne retourant que toutes les valeur en ordonnées des signaux passés par index.
        Args:
            index (int): index des channels devant être récupérés
        Returns:
            pandas.dataframe: données
        """

        if index>=self.n_samples:
            return None
        else:
            try:
                return self.data.iloc[index,:]
            except:
                print(f'{self.name} getYValues(): {index} / {self.n_samples}')

    def getDefaultPen(self,index:int=None):
        """ Méthode retournant le pinceau (couleur+type de trace) du signal en fonction de
            l'index qui lui ai passé

        Args:
            index (int): index de la courbe

        Returns:
            {pg.mkPen}: pen/pinceau de la courbe
        """
        if index is None:
            index = self.signalsCount

        if index >= self.n_colors:
            id_style = index // self.n_colors
            id_color = index % self.n_colors
        else:
            id_style = 0
            id_color = index
        return pg.mkPen(color=self.colors[id_color], style= self.penStyle[id_style])

    def to_dict(self):

        obj_params=self.get_file_loader_params()
        arg_to_export= ['signals']
        obj_params.update({k: v for k, v in self.__dict__.items() if k in arg_to_export })
        obj_params['signals'] = [sig.to_dict() for sig in obj_params['signals'].values()]

        return obj_params
    
    def get_file_loader_params(self):
        
        arg_to_export= ['file_type','import_params','address']
        obj_params = {k: v for k, v in self.__dict__.items() if k in arg_to_export }
        
        return obj_params

    def resolve_filter_references(self):
            """
            Résout toutes les références différées (ex: DiffFilter)
            après que tous les SignalObject ont été recréés.
            """
            # les analyses diff_external font référence à des signaux qui n'appartiennent pas
            # au même fileOBject, c'est donc à la fin du chargement de tout le workspace
            # qu'on peut résoudre ces références
            signal_map = { sig.name: sig   for sig in self.signals.values() }
            for sig in self.signals.values():
                for filter in sig.pipeline.values():
                    if filter.action_type.name == "DIFF":
                        filter.resolve_reference(signal_map)


    def signals_from_dict(self,data, filter_factory,analyses_factory):

        for sig_data in data["signals"]:
            sig = SignalObject.from_dict(self, sig_data, filter_factory,analyses_factory)
            self.signals[sig.id] = sig
        self.resolve_filter_references()

    def get_raw_y(self,name):
        """Vraies données brutes."""
        return np.array(self.data[name].values.tolist())

    def get_raw_x(self):
        """Vraies données brutes."""
        return np.array(self.data.index.get_level_values(1).values.tolist())

class SignalObject:
    """
    Représente un signal, dont les données sont calculées dynamiquement
    grâce à un pipeline de filtres non destructif.
    """
    item_type = itemType.RAW
    PARAMETER_SCHEMA= {
                        'Curve name'    :{
                                            'type':'str',
                                            'default':None,
                                            "readonly": True,
                                            "key": "name"
                                        },
                        'Curve unit'    :{
                                            'type':'str',
                                            'default':"°C",
                                            "readonly": False,
                                            "key": "unit"
                                        },
                        'Curve Filters' :{
                                            'type': 'group',
                                            'expanded':True,
                                            'children':
                                                    {
                                                    'Filter curve':{
                                                                    'type':'action',
                                                                    "key": "filter_curve"
                                                                    },
                                                    'Cut-off frequency':{
                                                                        'type':'float',
                                                                        'limits':[0.00001,None],
                                                                        "readonly": False,
                                                                        "key": "cut_off_freq"
                                                                        },
                                                    }
                                        },
                        'Curve pen'     : {
                                            'type':'pen',
                                            'expanded':True,
                                            "readonly": False,
                                            "key": "pen"
                                            }
                    }

    def __init__(self,  file_obj: FileObject,  name: str, pen:pg.mkPen = None , is_digital=False):
        self.file = file_obj
        self.name = name
        # propriétés graphiques
        self.visible = True
        self.is_selected = False
        self.is_reference = False
        self.is_digital = is_digital
        self.unit =''
        self.pen = pen
        self.opts_dict = custom_struct_functions.generate_opts_dict(self.PARAMETER_SCHEMA)
        self.cut_off_freq=0.005
        self.filter_curve=False
        self.id = uuid.uuid4().hex
        
        self.pipeline = OrderedDict() # filter_id -> FilterNode
        self.analyses = OrderedDict() # analysis_id -> AnalysisNode

        #data version permet au dependency manager de répertorier les modifications/filtres
        #appliquer avant l'application d'une analyse
        self.data_version = 0
        # liste des modèles/signaux dérivés
        self.derived_signals = []

        # cache interne
        self._cache = None
        self._cache_valid = False

    # ---------------- BASIC RAW ACCESS ----------------

    @property
    def x(self):
        """Axe des abscisses (colonne 0 du DataFrame)."""
        return self.file.get_raw_x()

    @property
    def is_modified(self):
        """Le signal a-t-il subit une modification"""
        return len(self.pipeline.values())>0 #! orderedDict

    @property
    def display_name(self):
        """Le signal a-t-il subit une modification"""
        return self.name + (" *" if self.is_modified else "")

    @property
    def raw_y(self):
        """Vraies données brutes."""
        return self.file.get_raw_y(self.name)

    # ---------------- PIPELINE COMPUTATION ----------------
    def compute(self):
        """Calcule y en appliquant chaque filtre dans l`ordre."""
        if self._cache_valid:
            return self._cache

        y = self.raw_y.copy()
        if self.pipeline:
            for node in self.pipeline.values(): #! orderedDict
                y = node.apply(self.x, y)

        self._cache = y
        self._cache_valid = True
        return y

    @property
    def y(self):
        """Accès direct aux données calculées."""
        return np.array(self.compute())

    def invalidate(self):
        """À appeler lorsqu'un filtre est modifié, ajouté ou supprimé."""
        self._cache_valid = False

    def get_params(self):
        """Récupère l'ensemble des paramètres du signal sous forme de dictionnaire clé-valeur,
        à partir de la structure définie dans opts_dict."""

        return {key:getattr(self, key) for param_path,key in self.opts_dict.items()}

    def get_param(self,key):
        """Récupère la valeur d'un paramètre à partir de sa clé."""
        return getattr(self, key)

    def set_params(self,newParams):
        """Met à jour les paramètres du signal à partir d'un groupe de paramètres."""
        '''_params = custom_struct_functions.extract_parameter_values(   self.PARAMETER_SCHEMA,
                                                                    newParams)'''

        for key, value in newParams.items():
            setattr(self, key, value)


    def get_filter_by_id(self, filter_id):
        if filter_id is None:
            return None
        return self.pipeline.get(filter_id)

    def get_filter_index_by_id(self, filter_id):
        if filter_id is None:
            return None

        try:
            return list(self.pipeline.keys()).index(filter_id)
        except ValueError:
            return None

    def get_filter_by_index(self, index):
        if index is None:
            return None

        values = list(self.pipeline.values())

        if index < 0 or index >= len(values):
            return None

        return values[index]

    def get_filter_id_by_index(self, index):
        if index is None:
            return None

        keys = list(self.pipeline.keys())

        if index < 0 or index >= len(keys):
            return None

        return keys[index]

    # ------------------------------------------------------------------
    # Analyses
    # ------------------------------------------------------------------

    def get_analysis_by_id(self, analysis_id):
        if analysis_id is None:
            return None
        return self.analyses.get(analysis_id)

    def get_analysis_index_by_id(self, analysis_id):
        if analysis_id is None:
            return None

        try:
            return list(self.analyses.keys()).index(analysis_id)
        except ValueError:
            return None

    def get_analysis_by_index(self, index):
        if index is None:
            return None

        values = list(self.analyses.values())

        if index < 0 or index >= len(values):
            return None

        return values[index]

    def get_analysis_id_by_index(self, index):
        if index is None:
            return None

        keys = list(self.analyses.keys())

        if index < 0 or index >= len(keys):
            return None

        return keys[index]

    #### Helpers de recherche par ID et index ####


    def to_dict(self):

        arg_to_export= ['name','visible','pen','pipeline','analyses','is_reference']
        obj_params = {k: v for k, v in self.__dict__.items() if k in arg_to_export }
        obj_params['pipeline'] = [(n_id,node.to_dict()) for n_id,node in
                                    obj_params['pipeline'].items()] 
        obj_params['analyses'] = [(n_id,node.to_dict()) for n_id,node in 
                                    obj_params['analyses'].items()] 
        obj_params['pen']=custom_struct_functions.QPen_to_dict(self.pen)

        return obj_params

    @staticmethod
    def from_dict(file_obj, data, filter_factory,analysis_factory):


        sig             =   SignalObject(file_obj, data["name"])
        sig.visible     =   data.get("visible", True)
        sig.pen         =   custom_struct_functions.dict_to_QPen( data.get("pen"))

        #! Ordered dict n'est pas sérialisable ! 
        for node_id,node_data in data.get("pipeline", []): 
            node = filter_factory.create(node_data)
            sig.pipeline[node_id]=node 
        for node_id,node_data in data.get("analyses", []): 
            node = analysis_factory.create(node_data) 
            sig.analyses[node_id]=(node) 
        return sig


class DerivedSignalObject(SignalObject):
    """
    Signal dérivé (modèle, projection, calcul analytique).
    Contrairement à SignalObject, x et y sont stockés directement.
    """
    item_type = itemType.DERIVED
    PARAMETER_SCHEMA = {
                        'Curve name'    :{
                                            'type':'str',
                                            'default':None,
                                            "readonly": True,
                                            "key": "name"
                                        },
                        'Curve pen'     : {
                                            'type':'pen',
                                            'expanded':True,
                                            "readonly": False,
                                            "key": "pen"
                                            }
                    }

    def __init__(  self,
                    parent_signal: SignalObject,
                    name: str,
                    x: np.ndarray,
                    y: np.ndarray,
                    pen: pg.mkPen = None,
                    metadata: dict | None = None,
                ):
        
        # On NE passe PAS de FileObject
        self.file = parent_signal.file      # uniquement pour cohérence visuelle / hiérarchie
        self.parent_signal = parent_signal
        self.opts_dict = custom_struct_functions.generate_opts_dict(self.PARAMETER_SCHEMA)
        self.name = name
        self._x = np.asarray(x)
        self._y = np.asarray(y)

        self.visible = True
        self.is_selected = False
        self.is_reference = False

        self.pen = pen

        # Pas de pipeline pour un modèle
        self.pipeline = OrderedDict() #! orderedDict
        # Pas d’analyses imbriquées 
        self.analyses = OrderedDict() #! orderedDict
        self.derived_signals = []

        self.metadata = metadata or {}

        # Pas de cache dynamique
        self._cache = None
        self._cache_valid = True

    @property
    def x(self):
        """Abscisses du signal modèle."""
        return self._x

    @property
    def y(self):
        """Ordonnées du signal modèle."""
        return self._y

    def compute(self):
        return self._y

    def invalidate(self):
        pass


@dataclass(frozen=True)
class SignalReference:

    file_id: str
    signal_id: str




class Folder:
    item_type = itemType.FOLDER
    name: str

    def __init__(self, name="New folder"):
        
        self.id = id or uuid.uuid4().hex
        self.name = name
        self.visible = True
        self.is_selected = False



class SignalGroupObject:
    item_type = itemType.GROUP

    PARAMETER_SCHEMA = {
                        "Groupe name": {
                                        "type": "str",
                                        "default": "New group",
                                        "key": "name",
                                    },
                        "Appli Filter/Analyse/Macro": {
                                        'type': 'group',
                                        'expanded':True,
                                        'visible':False,
                                        'children':
                                                {
                                            
                                            "First modifier": {
                                                                    "type": "list",
                                                                    "default": "peak",
                                                                    "limits": ["subsample", "mean", "peak"],
                                                                    "key": "mask_1",
                                                                },
                                            'Add modifier':{
                                                            'type':'action',
                                                            "key": "add_modif"
                                                            },
                                            'Refresh modifiers':{
                                                            'type':'action',
                                                            "key": "update_modif"
                                                            },
                                                },
                                    }
                        
                    }

    def __init__(self, name="New group", id=None, reference=None):
        
        self.id = id or uuid.uuid4().hex
        self.name = name
        self.visible = True
        self.is_selected = False
        # ref_key -> SignalReference 
        self.references = OrderedDict()

        for ref in reference or []:
            self.add_reference(ref.file_id, ref.signal_id)

    def add_reference(self, file_id,signal_id):
        key = self.make_ref_key(file_id, signal_id)

        if key not in self.references:
            self.references[key] =SignalReference(
                                                    file_id=file_id,
                                                    signal_id=signal_id
                                                )

    def remove_reference(self, file_id,signal_id):
        key = self.make_ref_key(file_id, signal_id)
        self.references.pop(key, None)
    
    def set_visible(self, workspace, visible: bool):
        self.visible = visible

        for ref in self.references.values():
            sig = workspace.resolve_signal(ref.file_id, ref.signal_id)

            if sig is not None:
                sig.visible = visible

    @staticmethod
    def make_ref_key(file_id, signal_id):
        return f"{file_id}:{signal_id}"

    def to_dict(self):
        return {
            "id": self.id,
            "type": "GROUP",
            "name": self.name,
            "visible": self.visible,
            "reference": [
                {
                    "file_id": ref.file_id,
                    "signal_id": ref.signal_id,
                }
                for ref in self.references.values()
            ]
        }
    
    @classmethod
    def from_dict(cls, data):
        refs = [ SignalReference( file_id=ref["file_id"], signal_id=ref["signal_id"])
                    for ref in data.get("references", [])]

        group = cls( id=data.get("id"),
                    name=data.get("name", "New group", references=refs)
                    )

        group.visible = data.set("visible", True)

        return group


    
class Workspace:

    def __init__(self):
        self.files = OrderedDict()  # list[FileObject] #! passage en ordered dict
        self.groups = OrderedDict()
        self.reference_signal = None

    def add_file(self, file_obj):
        self.files[file_obj.id] = file_obj

    def add_group(self, group_obj):
        self.groups[group_obj.id] = group_obj
    
    def resolve_signal(self,file_id,signal_id):
        file_obj = self.files.get(file_id)
        if file_obj is None:
            return None
        return file_obj.signals.get(signal_id)
    
    def set_file_visible(self,file_id,visible):
        file_obj = self.files.get(file_id)
        if file_obj is not None:
            file_obj.set_visible(visible)
    
    def set_group_visible(self,group_id,visible):
        group_obj = self.files.get(group_id)
        if group_obj is not None:
            group_obj.set_visible(visible)
    
    def set_reference_signal(self, signal : SignalObject):
        # désactiver l’ancienne référence
        if self.reference_signal is not None:
            self.reference_signal.is_reference = False

        self.reference_signal = signal

        if signal is not None:
            signal.is_reference = True
            
    def resolve_signal_ref(self, ref: SignalReference):
        file_obj = self.files.get(ref.file_id)
        
        if file_obj is None:
            return None
        return file_obj.signals.get(ref.signal_id)
    
    def to_dict(self):
        return {
                "version": "1.0",
                "workspace": {
                            "files": [f.to_dict() for f in self.files]
                            }
                }


    def save(self, path):
        with open(path, "w", encoding="utf-8") as f:
            export=self.to_dict()
            json.dump(export, f, indent=2)

    @staticmethod
    def load(path, filter_factory):

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        ws = Workspace()
        file_names=[]
        for file_data in data["workspace"]["files"]:

            file_obj = FileObject.from_dict(file_data, filter_factory)
            ws.add_file(file_obj)
            file_names.append(file_obj.name)

        # Après avoir créé tous les FileObject et SignalObject,
        # on peut résoudre les références différées (ex: diff_external)
        for file_id,file_obj in ws.files.items():
            for sig in file_obj.signals.values():
                for analysis in sig.analyses.value():
                    #! analysis.id = data["id"] <= il faut recharger l'id sauvegardé
                    if analysis.action_type.name == "DIFF_EXT":
                        ref_file =  [   file for file in ws.files if
                                        file.name == analysis.params['reference_file']][0]
                        analysis.resolve_reference({s.name: s for s in ref_file.signals.values()})

        return ws



