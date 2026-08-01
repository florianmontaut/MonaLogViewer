import pandas as pd
import numpy as np
import csv,json,re,datetime
from collections import namedtuple

from PyQt6 import QtGui,QtCore,QtWidgets
from ressources import (custom_functions,custom_items,custom_types,
                        custom_dialogs,custom_exceptions)
from model.base_objects import Workspace,FileObject
from model.filters.filter_factory import FilterFactory
from model.analysis.analysis_factory import AnalysisFactory

class ImportController(QtCore.QObject):


    file_signal = QtCore.pyqtSignal(FileObject)
    project_signal = QtCore.pyqtSignal(Workspace)

    def __init__(self,view: QtWidgets.QMainWindow,**opts):

        super().__init__()
        self.view = view
        self._from_project = custom_types.ImportMode.INTERACTIVE
        self.load_dict = {
                            custom_types.fileType.GL:
                            custom_items.ImportRequest(
                                                    file_format=custom_types.fileType.GL,
                                                    loader_label=(  "Loading GL files",
                                                                    "csv Files (*.csv)"),
                                                    loader= self.openGLCsvFiles
                                                    ) ,
                            custom_types.fileType.TXT:
                            custom_items.ImportRequest(
                                                    file_format=custom_types.fileType.TXT,
                                                    loader_label=("Loading .txt files",
                                                                "txt Files (*.txt),csv Files (*.csv)"),
                                                    loader= self.openTxt
                                                    ),
                            custom_types.fileType.CSV:
                            custom_items.ImportRequest(
                                                    file_format=custom_types.fileType.CSV,
                                                    loader_label=("Loading .csv files",
                                                                "csv Files (*.csv)"),
                                                    loader= self.openCsvFiles
                                                    ),
                            custom_types.fileType.JSON:
                            custom_items.ImportRequest(
                                                    file_format=custom_types.fileType.JSON,
                                                    loader_label=("Loading .json project files",
                                                                "json Files (*.json)"),
                                                    loader= self.openProject
                                                    )
                        }
        self.file_caracs = {
                            'CVS'               :   'Serial number',
                            'record_date'       :   'Date of event',
                            'record_time'       :   'Time of event',
                            'num_curves'        :   'analog traces',
                            'sampling'          :   'Sampling Period',
                            'log_id'            :   'File Id',
                            'event_name'        :   'Event name',
                            'event_occurences'  :   'Event number of occurences',
                            'data'              :   'Range max'
                            }
        
        self.txt_import_settings={}
        default_time = datetime.datetime.now()

        self.opts={
        "remove_old_graph"          : False,
        "remove_overrange"          : True,
        "auto_filter"               : False,
        "datetime_active"           : False,
        "downsample_signals"        : False,
        "downsample_ratio"          : 10,
        "downsample_type"           : "Peak",
        "downsample_thres"          : 10,
        "default_sampling_txt"      : 20*10**-3,
        "default_sampling_csv"      : 1,
        "default_time"              : default_time,
        "n_samples"                 : 898,
        "custom_folder"             :  "",
        "latest_import"             : True,
        "default_delimitor"         : ";",
        "default_unit_separator"    : ","
        }

        if opts:
            self.updateOptions(**opts)

    @property
    def defaultAdress(self):
        if self.opts['latest_import']:
            return self.view.latest_dir
        else:
            if self.opts['custom_folder']:
                return self.opts['custom_folder']
            else:
                return self.view.default_dir

    def updateOptions(self,opts):

        self.opts.update(opts)

    def openGLCsvFiles(self,fname,settings=None):
        """
        Méthode permettant de charger des fichiers .CSV de type GLviewer dans l'appli
        Arguments:
                fnames   --
        Returns:
                None     --
        """

        with open(fname, 'r') as csvfile:

            rawtxt = list(csv.reader(csvfile, delimiter=';'))
            file_caracs={}
            file_caracs.update(self.file_caracs)
            # listes des phrases clées par ordre d'apparition dans un fichier csv classique

            # création du générateur n permettant de simplifier la boucle for de recherche
            key_gen=(attribut for attribut in file_caracs.values())
            #index des caractéristiques du fichier
            id_caracs = {key : None for key in file_caracs.keys()}
            #la première phrase recherchée 'Sampling'est chargée dans a
            attribut=next(key_gen)

            #la boucle qui suit relève les numéros des lignes contenants les éléments
            #recherchés:
            for index,element in enumerate(rawtxt):
                if index >=100 :
                    break
                if not element:
                    continue
                try:
                    
                    if custom_functions.contains_header(element[0],attribut) is not None:
                        key=[key for key,val in file_caracs.items() if val == attribut][0]
                        id_caracs[key] = index
                        if attribut != 'data':
                            attribut = next(key_gen)#on charge la nouvelle phrase recherchée
                        else:
                            print('passage')
                            continue
                except StopIteration as e:
                    if not any(id_caracs.values()):
                        raise custom_exceptions.CsvStructureError(
                                                "le fichier .csv n'est pas au format"+
                                                " DALO."
                                                ) from e
                    break
            #print(f'Dernière phrase: {rawtxt[-1]}')
            channels=[]
            for key,val in file_caracs.items():
                
                line = rawtxt[id_caracs[key]][0]
                if key!='data':
                    value = line[line.find(':')+1:].strip()
                    file_caracs[key] = value
                else :
                    
                    row_num=id_caracs[key]

                    #contruction du span: max,min,unit
                    span_max = [channel_name for channel_name in rawtxt[row_num][1:]]
                    span_min = [channel_name for channel_name in rawtxt[row_num+1][1:]]
                    color = [channel_name for channel_name in rawtxt[row_num+2][1:]]
                    color.extend(['WHITE' for _ in range(len(span_max)-len(color))])
                    names = [channel_name for channel_name in rawtxt[row_num+3][1:]]
                    cpt=0
                    #print(f"nombre de signaux analogiques: {file_caracs['num_curves']}")
                    for name,max,min,color in zip(names,span_max,span_min,color):
                        #print(f"Digital signal? {name} / {cpt>int(file_caracs['num_curves'])}")
                        if cpt<int(file_caracs['num_curves']):
                            is_digital=False
                        else:
                            is_digital=True
                        
                        channels.append({
                                            'name'          : name,
                                            'min'           : max,
                                            'max'           : min,
                                            'color'         : color,
                                            'is_digital'    : is_digital
                                        })
                        cpt+=1
                    
                    #pour éviter la pluspart des problématiques du à l'introduction d'espaces
                    #retour à la ligne on cherche chacun des éléments et leur index plutôt
                    #que d'imposer un index fixe (il existe de multiple template des extracts
                    # GLviewer, selon la version du firmware, software ou du GL en lui-même)
                    first_data_row=id_caracs['data']+4
                    last_data_row=self.opts['n_samples']+first_data_row
                    print(f'1ere ligne des datas: {first_data_row} / Dernière ligne des data: {last_data_row}')
                    df=pd.DataFrame([row[1:] for row in rawtxt[first_data_row:last_data_row]],columns=names)
            for signal in names:
                df[signal]=pd.to_numeric(df[signal],errors='coerce')
            file_caracs['sampling']     = float(file_caracs['sampling'])*10**-9
            #insertion d'une colonne Time en première position dans le dataframe
            #print(f'ligne 198 (import_controller.py): {df.shape}')
            df.insert(  loc=0,
                        column='Time',
                        value=np.linspace(  0,
                                            (self.opts['n_samples']-1)*
                                            file_caracs['sampling'],
                                            self.opts['n_samples']
                                        )-0.8
                        )
            #configuration de la colonne Time comme index du dataframe
            data=df.set_index('Time',append=True)
            file_struct=custom_items.FileStruct(
                                                address         = fname,
                                                file_type       = custom_types.fileType.GL.name, #! on modifiera les types
                                                sampling        = file_caracs['sampling'],
                                                n_samples       = self.opts['n_samples'],
                                                recordDate      = self.opts["default_time"],
                                                data            = data,
                                                import_params   = {
                                                'check_table': [True for _ in range(len(channels))],
                                                'channels_setting': channels,
                                                'CVS_num':file_caracs['CVS'],
                                                'log_id':file_caracs['log_id'],
                                                'event_name': file_caracs['event_name'],
                                                'event_occurences':file_caracs['event_occurences'],
                                                'event_date':(  file_caracs['record_date'],
                                                                file_caracs['record_time'])
                                                }
                                                )   

            if self._from_project == custom_types.ImportMode.INTERACTIVE:

                self.send_file_to_workspace(file_struct)
            else:
                return file_struct

    def _get_import_settings(self,params):
        self.txt_import_settings=params

    def ImportWizard(self,adress,params=None):

        if params is None:
            delim       = None
            unitDelim   = None
        else:
            delim       = params.get('delim',None)
            unitDelim   = params.get('unitDelim',None)
            
        if delim is None:
            delim = self.opts["default_delimitor"]
        if unitDelim is None:
            unitDelim = self.opts["default_unit_separator"]

        userInput = custom_dialogs.ImportWizardDialog(
                                                        adress=adress,
                                                        delimitor=delim,
                                                        unitDelim=unitDelim
                                                    )
        userInput.params_ready.connect(self._get_import_settings)

        result = userInput.exec()
        if result != QtWidgets.QDialog.DialogCode.Accepted:
            return None

        settings = self.txt_import_settings or userInput.collect_params()
        self.txt_import_settings = settings

        return self.openTxt(adress, settings)


    def ImportErrorUserWarning(self,errorStruct):

        #?revoir le principe de dictionnaire qui semble alambiqué
        format_dict=    {custom_types.fileType.GL:"Graphtec CSV file",
                        custom_types.fileType.JSON:"JSON file",
                        custom_types.fileType.TXT:"Plain Txt file",
                        custom_types.fileType.CSV:"Plain CSV file"}

        userInput = custom_dialogs.ImportErrorDialog(error = errorStruct[0],
                                                currentFormat = errorStruct[1],
                                                importFormats = format_dict)

        userInput.accepted.connect(lambda: self.loaderSelect(
                                                    (userInput.getFormat(),
                                                    [errorStruct[2]])
                                                    ))
        userInput.show()



    def openCsvFiles(self,fname,mode_etuve=False,settings=None):
        """
        Méthode permettant de charger un fichier .csv exporter par l'automate du CHILLER
        Arguments:
                None   --
        Returns:
                None   --
        """
        file_caracs=self.file_caracs
        with open(fname, 'r') as csvfile:

            dialect = csv.Sniffer().sniff(csvfile.read(4096), delimiters=';,\t')
            csvfile.seek(0)
            rawtxt      = list(csv.reader(csvfile, dialect))
            n_points    = len(rawtxt)-1
            sampling    = self.opts["default_sampling_csv"]
            start_time  = self.opts["default_time"]
            channels    =[]
            check_table =[]

            for val in rawtxt.pop(0):
                if val:
                    channels.append(val)
            channels.pop(0)
            #si le nombre de channels est égale au nombre de colonnes des data,
            #il faut alors retirer les colonnes X en doublon
            if (len(channels)+1)==len(rawtxt[1]):
                if channels[0]=="Temp_amb":
                    mode_etuve=True
                    channels=channels[0::1]
                else:
                    channels=channels[1::2]
                    mode_etuve=False
            if mode_etuve==True:
                data=[line[1::1] for line in rawtxt]
                #!écrase le sampling par défaut
                sampling=int(rawtxt[2][0])-int(rawtxt[1][0])
            else:
                data=[line[1::2] for line in rawtxt]
            df=pd.DataFrame(data,columns=channels)
            for signal in channels:
                df[signal]=pd.to_numeric(df[signal],errors='coerce')
                # TODO channels span: faut-il vérifier la validité des données sur un fichier csv?
                channels_span=1000
                check_table.append(self.isChannelValid(df[signal],
                                                            channels_span,
                                                            active=self.opts["remove_overrange"]))

            df.insert(loc=0,column='Time',value=np.linspace(0,(n_points-1)*sampling,n_points))
            data=df.set_index('Time',append=True)

            file_caracs=custom_items.FileStruct(
                                                address         = fname,
                                                file_type       = custom_types.fileType.CSV.name,
                                                sampling        = sampling,
                                                n_samples       = n_points,
                                                recordDate      = start_time,
                                                import_params   = {'check_table': check_table},
                                                data            = data
                                            )
            if self._from_project == custom_types.ImportMode.INTERACTIVE:
                self.send_file_to_workspace(file_caracs)
            else:
                return file_caracs

    def openTxt(self,fname,settings=None):
        """
        Méthode permettant de charger un fichier .txt (exemple enregistrement des NTCs via matis)
        Arguments:
                None   --
        Returns:
                None   --
        """
        file_caracs=self.file_caracs
        default_settings={
                    'delim'             :';,\t',
                    'unitdelim'         : '.',
                    'start'             : 0,
                    'columns'           : [],
                    'sigNames'          : True,
                    'isFirstColIndex'   : False,
                }
        with open(fname,encoding="utf-8-sig") as csvfile:

            if settings is None:
                settings = default_settings

            dialect = csv.Sniffer().sniff(csvfile.read(4096), delimiters=settings['delim'])
            csvfile.seek(0)
            rawtxt = list(csv.reader(csvfile, dialect))
            n_points = len(rawtxt) - 1 if settings['sigNames'] else 0
            start_time = self.opts["default_time"]
            channels = []
            check_table = []
            #si la première ligne correspond au noms des signaux on les récupères
            if settings['sigNames']:
                for n,val in enumerate(rawtxt.pop(0)):
                    if val and n not in settings['columns'] :
                        channels.append(val)
            #sinon on en créé
            else:
                for n in range(len(rawtxt[0])):
                    channels.append(f'channel{n}')
            data=[]
            #print(f'File delim: {settings["delim"]} / Unit delim: {settings["unitdelim"]}')
            try:
                for line in rawtxt[settings['start']:]:
                    values=[float(val.replace(settings['unitdelim'],'.'))
                            for n,val in enumerate(line) if n not in settings['columns']]
                    data.append(values)
            except Exception as e:

                raise custom_exceptions.TxtDelimiterError(f"Failed to load TXT file {fname}"
                                                            ) from e

            df=pd.DataFrame(data,columns=channels)
            for signal in channels:
                df[signal]=pd.to_numeric(df[signal],errors='coerce')
                # TODO: channels span: faut-il vérifier la validité des données
                # sur un fichier csv?
                channels_span=(200,-20 )
                check_table.append(self.isChannelValid( df[signal],
                                                        channels_span,
                                                        active=self.opts["remove_overrange"]))
            if not settings['isFirstColIndex']:
                sampling=self.opts["default_sampling_txt"]
                df.insert(  loc=0,
                            column='Time',
                            value=np.linspace(0,(n_points-1)*sampling,n_points))
            else:
                sampling=df.iat[1,0]-df.iat[0,0]
            data=df.set_index(df.columns[0],append=True)

            file_caracs=custom_items.FileStruct(
                                                address         = fname,
                                                file_type       = custom_types.fileType.TXT.name,
                                                sampling        = sampling,
                                                n_samples       = n_points,
                                                recordDate      = start_time,
                                                import_params   = settings,
                                                data            = data,
                                            )
            if self._from_project == custom_types.ImportMode.INTERACTIVE:
                self.send_file_to_workspace(file_caracs)
            else:
                return file_caracs
            #self._model.MAJ_files.emit()
            #Emit réalisé dans le model à la fin de la méthode newFile pour
            #éviter tout problème de synchro

    def send_file_to_workspace(self,file_caracs:custom_items.FileStruct):

        # Création du modèle métier
        file_obj = FileObject(file_caracs)
        # Ajouter chaque colonne comme signal brut
        for col in file_obj.data.columns[:]:
            file_obj.add_signal(col)
        self.file_signal.emit(file_obj)


    @staticmethod
    def isChannelValid(data,threshold,active,ratio=0.9)->bool:
        """
        Méthode permettant de vérifier si les données du channel sont valides
        ex: un thermocouple mal connecté). Si 90% des données sont les bornes définis
        du channel, on considère que les données sont valides.
        Arguments:
                data        {pandas.series} signal
                threshold   {tuple(float,float} seuils à partir des quels les données sont
                                                considérées comme erronées
                active       {bool}         l'option de filtrage des signaux est elle active
                ratio       {float}         ratio des données erronnées sur la totalité des
                                            points à depassser pour déclarer le signal comme
                                            non valide
        Returns:
                {bool}                      resultat du channel est-il valide ?
        """
        if not active:
            return True
        else:
            if ratio<0 or ratio>1 :
                raise ValueError
            data_len=data.size
            validation_list=data.between(threshold[0],threshold[1])
            #retourne l'état de cette comparaison : somme(validation) > seuil = signal OK
            return sum(validation_list)>ratio*data_len

    @staticmethod
    def convertDate(date):

        date_str =' '.join(date)
        if '-'in date_str:
            date_format = '%d-%m-%Y %H:%M:%S'
            try:
                date_obj = datetime.datetime.strptime(date_str, date_format)
            except ValueError:
                date_format = '%Y-%m-%d %H:%M:%S'
                try:
                    date_obj = datetime.datetime.strptime(date_str, date_format)
                except ValueError:
                    return "Failed date conversionn with '-' separator"
        elif '/'in date_str:
            date_format = '%d/%m/%Y %H:%M:%S'
            try:
                date_obj = datetime.datetime.strptime(date_str, date_format)
            except ValueError:
                date_format = '%Y/%m/%d %H:%M:%S'
                try:
                    date_obj = datetime.datetime.strptime(date_str, date_format)
                except ValueError:
                    return "Failed date conversionn with '-' separator"
        else:
            return None

        return date_obj
        #On remplace "Trigger time" par sa valeur. "Start time" ne correspond
        #pas au début de l'enregistrement

    def openProject(self,fname,settings=None):

        self._from_project=custom_types.ImportMode.RESTORE
        with open(fname, "r", encoding="utf-8") as f:
            data = json.load(f)

        ws = Workspace()
        for file_data in data["workspace"]["files"]:
            file_type=custom_types.fileType[file_data['file_type']]
            while True:
                try:
                    import_request:custom_items.ImportRequest = self.load_dict[file_type]
                    file_caracs=import_request.loader(  file_data['address'],
                                                        file_data['import_params'])
                    break
                except custom_exceptions.TxtDelimiterError  as e:
                    QtWidgets.QMessageBox.warning(self,
                                        "Séparateur des colonnes invalide",
                                        str(e)+
                                        '\n Veuillez vérifier le type de séparaterur utilisé.')
                    file_caracs = self.ImportWizard(file_data['address'])
                    if file_caracs is None:
                        raise custom_exceptions.TxtFormatError(
                            f"Import cancelled for {file_data['address']}"
                        )
                    break
                except custom_exceptions.TxtFormatError  as e:
                    QtWidgets.QMessageBox.warning(self,
                                        "Format invalide",
                                        str(e)+'\n Veuillez vérifier le format du fichier.')
                    file_caracs = self.ImportWizard(file_data['address'])
                    if file_caracs is None:
                        raise custom_exceptions.TxtFormatError(
                            f"Import cancelled for {file_data['address']}"
                        )
                    break

            file_obj = FileObject(file_caracs)
            file_obj.signals_from_dict(file_data, FilterFactory(),AnalysisFactory())
            ws.add_file(file_obj)

        self._from_project=custom_types.ImportMode.INTERACTIVE
        self.project_signal.emit(ws)


    def loaderSelect(self,loadStruct:dict):
        """
        Méthode gérant la réception des données du viewer. Cette dernière utilise la méthode
        liée à l'extension du(es) fichier(s) à charger. Seul plusieurs fichiers du même type
        (GL/CSV/TXT) peuvent être chargés par la méthode loaderSelect.

        Arguments:
                fname      --
                fileType   --
        Returns:
                None        --
        """

        fileType    =   custom_types.fileType[loadStruct["file_type"]]
        fname       =   loadStruct["address"]
        params      =   loadStruct["import_params"]

        try:
            import_request=self.load_dict[fileType]
            message,_ = import_request.loader_label
            self.view.statusbar.showMessage(message,3000)
            import_request.loader(fname=fname,settings=params)
        except custom_exceptions.TxtDelimiterError  as e:
            QtWidgets.QMessageBox.warning(self,
                                "Séparateur des colonnes invalide",
                                str(e)+'\n Veuillez vérifier le type de séparaterur utilisé.')
            self.ImportWizard(fname,params)
        except custom_exceptions.TxtFormatError  as e:
            QtWidgets.QMessageBox.warning(self,
                                "Format invalide",
                                str(e)+'\n Veuillez vérifier le format du fichier.')
            self.ImportWizard(fname,params)
        except custom_exceptions.CsvStructureError  as e:
            QtWidgets.QMessageBox.warning(self,
                                "Structure de donnée invalide",
                                str(e)+'\n Veuillez vérifier la structure du fichier CSV.')
            self.ImportWizard(fname,params)
        except custom_exceptions.GLStructureError  as e:
            QtWidgets.QMessageBox.warning(self,
                                "Structure de donnée invalide",
                                str(e)+'\n Veuillez vérifier la structure du fichier GL.')
            self.ImportWizard(fname,params)
        except Exception as err:
            errorStruct=[err,fileType,fname,params]
            self.ImportErrorUserWarning(errorStruct)


    def load_file_dialog(self,fileType:custom_types.fileType,adress=None):
        """
        Méthode gérant la fenêtre de dialogue permettant de charger des fichiers .CSV
        de type GLviewer dans l'appli.

        Arguments:
                adress      --
                fileType    --
        Returns:
                None        --
        """
        
        import_request : custom_items.ImportRequest = self.load_dict[fileType]

        message,file_extension = import_request.loader_label
        self.view.statusbar.showMessage(message,3000)
        fname,_ = QtWidgets.QFileDialog.getOpenFileName(  self.view,"Open file",
                                                                self.defaultAdress,
                                                                file_extension)
        if not fname:
            return

        if isinstance(fname,list):
            fname=fname[0]

        try:
            self.view.statusbar.showMessage(f"Loading file: {fname}",3000)
            import_request.loader(fname=fname)
        except Exception as e :
            print(f'Import failed: {e}')
            self.ImportWizard(fname)