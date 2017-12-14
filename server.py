import socket

HOST = ''
PORT = 50007
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind((HOST,PORT))
s.listen(1)
while 1:
    conn, addr = s.accept()
    print 'Connected by', addr
    data = conn.recv(1024)
    print(data)
conn.close()
