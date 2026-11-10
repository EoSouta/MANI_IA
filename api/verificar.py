print("TESTE PYTHON FUNCIONANDO!")
 
import sqlite3
 
conexao = sqlite3.connect("mani.db")
cursor = conexao.cursor()
 
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
 
for tabela in cursor.fetchall():
    print("Tabela:", tabela[0])
 
conexao.close()
