import os
import sqlite3

from SoggyVision.core import DB_DIR
from SoggyVision.acs import ACSFlags, ACSData, ACSMetadata


class ACSFlagsTable:
    name = 'acs_flags'
    fields = list(ACSFlags.__annotations__.keys())
    dtypes = ['TEXT' if issubclass(v,(str,bytes,list)) else "BIGINT" if issubclass(v, int) else "FLOAT" if issubclass(v,float) else "TEXT" for v in list(ACSFlags.__annotations__.values())]

class ACSMetadataTable:
    name = 'acs_metadata'
    fields = list(ACSMetadata.__annotations__.keys())
    dtypes = ['TEXT' if issubclass(v,(str,bytes,list)) else "BIGINT" if issubclass(v, int) else "FLOAT" if issubclass(v,float) else "TEXT" for v in list(ACSMetadata.__annotations__.values())]

class ACSDataTable:
    name = 'acs_data'
    fields = list(ACSData.__annotations__.keys())
    dtypes = ['TEXT' if issubclass(v,(str,bytes, list)) else "BIGINT" if issubclass(v, int) else "FLOAT" if issubclass(v,float) else "TEXT" for v in list(ACSData.__annotations__.values())]


class SVDB():
    def __init__(self,database_name):
        os.makedirs(DB_DIR,exist_ok=True)
        self.dbcon = sqlite3.connect(os.path.join(DB_DIR,f"{database_name}.db"))
        self.dbcur = self.dbcon.cursor()

        self.build_table(ACSDataTable.name, ACSDataTable.fields, ACSDataTable.dtypes)
        self.build_table(ACSFlagsTable.name, ACSFlagsTable.fields, ACSFlagsTable.dtypes)
        self.build_metadata_table(ACSMetadataTable.name, ACSMetadataTable.fields, ACSMetadataTable.dtypes)


    def build_metadata_table(self, table_name, fields, dtypes):
        table_name = table_name.lower()
        fields_dtypes = dict(zip(fields, dtypes))
        fields_dtypes_str = ', '.join([' '.join([k, v]) for k, v in fields_dtypes.items()])
        statement = f"CREATE TABLE IF NOT EXISTS {table_name}({fields_dtypes_str})"
        self.dbcur.execute(statement)

    def build_table(self, table_name, fields, dtypes):
        table_name = table_name.lower()
        fields_dtypes = dict(zip(fields, dtypes))
        pk = 'time'
        fields_dtypes_str = ', '.join([' '.join([k, v]) for k, v in fields_dtypes.items()]) + f", PRIMARY KEY ({pk})"
        statement = f"CREATE TABLE IF NOT EXISTS {table_name}({fields_dtypes_str})"
        self.dbcur.execute(statement)


    def insert_data(self, table_name, fields, data):
        table_name = table_name.lower()
        statement = f"INSERT INTO {table_name}({', '.join(fields)}) VALUES ({', '.join(['?' for i in range(len(data))])})"
        self.dbcur.execute(statement, data)
        self.dbcon.commit()


    def get_all_data(self, table_name):
        table_name = table_name.lower()
        statement = f"SELECT * FROM {table_name}"
        self.dbcur.execute(statement)
        data = self.dbcur.fetchall()
        return data

    def select_data(self, table_name, fields):
        table_name = table_name.lower()
        field_str = ', '.join(fields)
        statement = f"SELECT {field_str} FROM {table_name}"
        self.dbcur.execute(statement)
        data = self.dbcur.fetchall()
        return data


    def update_end_time(self, table_name, begin_time, end_time):
        statement = f"UPDATE {table_name} SET end_time='{end_time}' WHERE begin_time='{begin_time}'"
        self.dbcur.execute(statement)
        self.dbcon.commit()
