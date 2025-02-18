#!/usr/bin/env python
import sys
import signal
import subprocess
import socket
import os
import time
import tempfile
import json
import select


class Termuxmpv:
    def signal_handler(self, signal, frame):
        pass

    def __init__(self, args):
        signal.signal(signal.SIGINT, self.signal_handler)
        self.args = args
        self.lastCommand = ""
        self.pause = False
        self.metadata = {}
        self.initFifo()
        if not self.checkForSocket():
            self.createSocket()
        self.startProcess()
        self.getSocket()
        self.setupPropertyChanges()
        self.updateNotification()
        self.monitor()

    def __del__(self):
        self.cleanup()

    def checkForSocket(self):
        prev = ""
        for arg in reversed(self.args):
            if arg == "--input-ipc-server":
                self.sockpath = prev
                return True
            elif arg.startswith("--input-ipc-server="):
                self.sockpath = arg.split("=")[1]
                return True

            prev = arg
        return False

    def initFifo(self):
        self.notificationId = "termuxMpv.{}".format(time.time())
        self.fifoname = "/data/data/com.termux/files/usr/tmp/{}".format(
            self.notificationId
        )
        os.mkfifo(self.fifoname)
        self.fifo = os.open(self.fifoname, os.O_RDONLY | os.O_NONBLOCK)

    def startProcess(self):
        prefix = "/data/data/com.termux/files/usr"
        program = "{}/bin/mpv".format(prefix)
        self.mpvproc = subprocess.Popen(
            [program, "--input-ipc-server={}".format(self.sockpath)] + self.args,
            stdin=sys.stdin,
        )

    def createSocket(self):
        fd, self.sockpath = tempfile.mkstemp(prefix="mpv.")
        os.close(fd)
        os.remove(self.sockpath)

    def getSocket(self):
        while self.isRunning():
            time.sleep(0.1)
            try:
                self.sock = socket.socket(socket.AF_UNIX)
                self.sock.connect(self.sockpath)
            except (FileNotFoundError, ConnectionRefusedError):
                continue
            else:
                break

    def isRunning(self):
        if self.mpvproc.poll() is None:
            return True
        else:
            sys.exit(self.mpvproc.returncode)

    def cleanup(self):
        try:
            os.close(self.fifo)
        except OSError:
            pass
        try:
            os.remove(self.fifoname)
        except FileNotFoundError:
            pass
        if self.notificationId:
            command = ["termux-notification-remove", self.notificationId]
            subprocess.call(command)
        if self.sockpath:
            try:
                os.remove(self.sockpath)
            except OSError:
                pass
        self.updatehook()

    def monitor(self):
        while self.isRunning():
            # time.sleep(1)
            b = True
            buf = b""
            while b:
                b = None
                r, w, e = select.select([self.sock], [], [], 1)
                if r:
                    b = self.sock.recv(1024)
                if not b:
                    break
                buf += b
            buf = buf.decode("utf-8", "replace")
            newline = buf.find("\n")
            while newline >= 0:
                message = buf[: newline + 1]
                buf = buf[newline + 1 :]
                newline = buf.find("\n")

                self.processMessage(message)
            command = ""
            while True:
                part = os.read(self.fifo, 1024).decode("utf-8")
                command = "{}{}".format(command, part)
                if not part:
                    break
            if command:
                self.sendCommand(command)

    def setupPropertyChanges(self):
        i = 1
        for prop in ["pause", "metadata", "filename", "media-title"]:
            self.sendMessage(["observe_property", i, prop])
            i += 1

    def sendCommand(self, command):
        command = command.strip()
        if command == "prev":
            self.sendMessage(["keypress", "<"])
        if command == "next":
            self.sendMessage(["keypress", ">"])
        if command == "pause":
            self.sendMessage(["keypress", "p"])
        if command == "seek-back":
            self.sendMessage(["keypress", "left"])
        if command == "seek-back-far":
            self.sendMessage(["keypress", "down"])
        if command == "seek-forward":
            self.sendMessage(["keypress", "right"])
        if command == "seek-forward-far":
            self.sendMessage(["keypress", "up"])
        if command == "exit":
            self.sendMessage(["keypress", "q"])
        if command == "updateNotification":
            self.updateNotification()

    def sendMessage(self, message):
        data = {}
        data["command"] = message
        data = json.dumps(data)
        data = "{}\n".format(data)
        data = data.encode("utf-8")
        while data:
            try:
                size = self.sock.send(data)
            except BrokenPipeError:
                self.cleanup()
                sys.exit(170)
            if size == 0:
                print("Socket error", file=sys.stderr)
            data = data[size:]

    def processMessage(self, message='{"event":""}'):
        try:
            message = json.loads(message)
        except Exception:
            pass
        if "event" in message and "data" in message:
            if message["event"] == "property-change":
                if message["name"] == "pause":
                    self.pause = message["data"]
                if message["name"] == "metadata":
                    self.metadata = message["data"]
                if message["name"] == "filename":
                    self.filename = message["data"]
                if message["name"] == "media-title":
                    self.media_title = message["data"]
                self.updateNotification()

    def updatehook(self):
        command = "hook-update-mpv"
        devnull = open(os.devnull, "wb")
        try:
            subprocess.call(["sh", "-c", command], stdout=devnull, stderr=devnull)
        except Exception:
            pass

    def updateNotification(self):
        metadata = {}
        for attr in ["album", "artist", "title", "icy-title"]:
            try:
                metadata[attr] = self.metadata[attr]
            except KeyError:
                try:
                    metadata[attr] = self.metadata[attr.upper()]
                except KeyError:
                    metadata[attr] = "None"
        try:
            filename = self.filename
        except AttributeError:
            filename = "None"
        try:
            media_title = self.media_title
        except AttributeError:
            media_title = "None"
        if metadata["title"] != "None":
            title = metadata["title"]
        if metadata["icy-title"] != "None":
            title = metadata["icy-title"]
        else:
            title = media_title
        command = [
            "termux-notification",
            "--id",
            self.notificationId,
            "--group",
            "termux-mpv",
            "--alert-once",
            "--title",
            title,
            "--type",
            "media",
            "--content",
            "{}, {}".format(metadata["artist"], metadata["album"]),
            "--priority",
            "max",
            "--action",
            ";".join(
                [
                    "am start --user 0 -n com.termux/com.termux.app.TermuxActivity",  # noqa line break is unreasonable
                    "echo 'updateNotification'> {}".format(self.fifoname),
                ]
            ),
            "--media-previous",
            "echo 'prev'> {}".format(self.fifoname),
            "--media-play",
            "echo 'pause'> {}".format(self.fifoname),
            "--media-pause",
            "echo 'pause'> {}".format(self.fifoname),
            "--media-next",
            "echo 'next'> {}".format(self.fifoname),
            "--on-delete",
            "echo 'exit'>{}".format(self.fifoname),
        ]
        if self.pause:
            command += [
                "--icon",
                "pause",
            ]
        else:
            command += [
                "--icon",
                "play_arrow",
            ]
        if self.lastCommand != command:
            self.lastCommand = command
            self.updatehook()
            subprocess.call(command)


def main(args=None):
    if args is None:
        args = sys.argv[1:]
    Termuxmpv(args)


if __name__ == "__main__":
    main()
