import devices
import socket

r = devices.Recognizer()
m = devices.Microphone()
temp_value = ["speech :"]
try:
    print("A moment of silence, please...")
    with m as source: r.adjust_for_ambient_noise(source)
    print("Set minimum energy threshold to {}".format(r.energy_threshold))
    while True:
        print("Say Something")
        with m as source: audio = r.listen(source)
        print("listen function returns a value")
        try:
            temp_value = ["speech :"]
            #socket
            HOST = ''
            PORT = 6666
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            value = r.recognize_sphinx(audio)
            print("you said {}".format(value))
            s.connect((HOST,PORT))
            s.sendall("speech: "+value)
            print("sending")
            s.close()
            print("closing")
        except devices.UnKnownValueError:
            print("Oops! Didn't catch that")
except KeyboardInterrupt:
    pass

