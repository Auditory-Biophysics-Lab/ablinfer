import io
import gzip
import logging
import os
import queue
import threading
import time

try:
    import sys
    import SimpleITK as sitk
except ImportError:
    HAS_SITK = False
else:
    HAS_SITK = True

try:
    import itk
except ImportError:
    HAS_ITK = False
else:
    HAS_ITK = True

if not HAS_ITK and not HAS_SITK:
    logging.warning("SimpleITK and ITK are both unavailable, file conversion will not work")

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

def can_convert(fromext: str, toext: str):
    """Figure out if we can (likely) convert from one extension to another.

    :param fromext: The source extension, including leading period.
    :param toext: The destination extension, including leading period.
    """
    good = (".nii", ".nii.gz", ".nrrd",)

    return (HAS_SITK or HAS_ITK) and fromext.lower() in good and toext.lower() in good

def convert_image(source: str, dest: str):
    """Run the source through ITK/SimpleITK to produce the destination.

    This function is intended to be called after :py:func:`can_convert` to try to actually do the 
    conversion; note that it requires the files to be on disk.

    :param source: The source filename.
    :param dest: The destination filename.
    """
    if HAS_SITK:
        im = sitk.ReadImage(source)
        sitk.WriteImage(im, dest)
    elif HAS_ITK:
        im = itk.imread(source)
        itk.imwrite(im, dest)
    else:
        raise Exception("No conversion library is available!")
