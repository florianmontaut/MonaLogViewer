import csv
import pandas as pd


def openTxt(fname):
    """
    Méthode permettant de charger un fichier .txt (exemple enregistrement des NTCs via matis)
    Arguments:
            None   --
    Returns:
            None   --
    """
    
    default_settings={
                    'delim'             :'\t',
                    'unitdelim'         : '.',
                    'start'             : 0,
                    'columns'           : [],
                    'sigNames'          : True,
                    'isFirstColIndex'   : False,
                    }
    channels=[]
    with open(fname,encoding="utf-8-sig") as csvfile:
        
        csvfile.seek(0)
        rawtxt = list(csv.reader(csvfile, delimiter='\t'))
        first_data_line=0
        channels=[]
        for n,line in enumerate(rawtxt):
            ([word for word in line])
            
            if line:
                if line[0]=='Date':
                    first_data_line=n+1
                    channels=[word for word in line][2:]
                    break
        print(channels)
        #suppression des lignes offLine
        data=[[float(value) for value in line[3:-1]] for line in rawtxt[first_data_line:] if len(line)>1]
        print(data[0])
        print(len(data[0]),len(channels))
        df=pd.DataFrame(data,columns=channels)
        print(df)


if __name__ == '__main__':
    
    openTxt('data.txt')