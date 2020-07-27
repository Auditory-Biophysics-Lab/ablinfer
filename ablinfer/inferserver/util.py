import io
import gzip
import queue
import threading
import time

class KeepAliveIterator:
    """Class for implementing iterators with keep-alives."""
    def __iter__(self):
        empty = False
        while True:
            with self.lock:
                if not self.running and self.queue.empty():
                    self.timer.cancel()
                    break
                if not empty:
                    self.last = time.time()
                empty = False
            try:
                yield self.queue.get(timeout=0.5)
            except queue.Empty:
                empty = True
            except GeneratorExit:
                with self.lock:
                    self.running = False
                    self.timer.cancel()
            
    def mainthread(self):
        for l in self.wrap:
            while True:
                try:
                    self.queue.put(l, timeout=0.5)
                except queue.Full:
                    with self.lock:
                        if not self.running:
                            return
                else:
                    break

            with self.lock:
                if not self.running:
                    return

        with self.lock:
            self.running = False

    def timeoutthread(self):
        with self.lock:
            delta = time.time() - self.last
            if not self.running:
                return
            elif self.queue.empty() and delta >= self.timeout:
                try:
                    self.queue.put(self.alt, block=False)
                except queue.Full:
                    pass
                delta = 0
            self.timer = threading.Timer(self.timeout-delta, self.timeoutthread)
            self.timer.start()


    def __init__(self, wrap, alt="\0\n", qsize=100, timeout=5):
        self.wrap = wrap
        self.queue = queue.Queue(maxsize=qsize)
        self.lock = threading.RLock()
        self.running = True
        self.alt = alt
        self.timeout = timeout
        self.last = time.time()

        self.main = threading.Thread(target=self.mainthread)
        self.main.start()
        self.timer = threading.Timer(timeout, self.timeoutthread)
        self.timer.start()

def guess_filetype(header: bytes, partial=""):
    """Try to guess the filetype.

    :param header: A sensible amount of the header, usually about a kilobyte.
    """

    if len(header) >= 2 and header[:2] == bytes((0x1f, 0x8b)): ## Probably GZIP
        bio = io.BytesIO(header)
        try:
            gz = gzip.GzipFile(fileobj=bio, mode="rb")
            ## First try to read enough for a NII header
            decomp = gz.read(384)
        except EOFError:
            ## Now try to read enough for a NRRD header
            try:
                gz.seek(0)
                decomp = gz.read(4)
            except EOFError:
                ## Now just give up
                return ".gz"+partial
        return guess_filetype(decomp, partial=".gz"+partial)
    elif len(header) >= 4 and header[:4] == b"NRRD": ## Probably NRRD
        return ".nrrd"+partial
    elif len(header) >= 384 and header[:2] == bytes((0x5c, 0x01)) and header[344:348] in (b"n+1\0", "ni1\0"): 
        return ".nii"+partial

    return None
