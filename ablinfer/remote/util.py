import requests as r
import time

class ProgressReporter:
    def _report(self, chunk_length):
        ct = time.monotonic()
        delta = ct - self.last
        self.avg = 0.8*self.avg + 0.2*(chunk_length/delta)
        self.running += chunk_length
        self.last = ct
        if ct-self.last_report > self.period:
            self.last_report = ct
            r_mib = self.running / 1048576
            t_mib = self.total / 1048576
            a_mib = self.avg / 1048576
            if self.total != -1:
                percent = min(1, max(0, self.running/self.total))
                self.func(percent, self.header + " %.1f/%.1f MiB (%.1f MiB/s)" % (r_mib, t_mib, a_mib))
            else:
                self.func(0, self.header + " %.1f/- MiB (%.1f MiB/s)" % (r_mib, a_mib))

    def report(self, chunk_length):
        self.toadd += chunk_length
        if self.toadd > 512*1024 or self.running+self.toadd == self.total:
            self._report(self.toadd)
            self.toadd = 0

    __call__ = report

    def __init__(self, total, header, func, period = 0):
        self.total = total
        self.running = 0
        self.header = header
        self.func = func
        self.last = time.monotonic()
        self.last_report = self.last
        self.avg = 0
        self.period = period
        self.toadd = 0

        func(0, header)

class FObjReadWrapper:
    def read(self, n=-1):
        buff = self.fp.read(n)
        self.pr(len(buff))

        return buff

    def tell(self):
        return self.fp.tell()

    def seek(self, n):
        return self.fp.seek(n)

    def __len__(self):
        return self.size

    def __init__(self, fp, size, header, func, period = 0):
        self.fp = fp
        self.size = size
        self.pr = ProgressReporter(size, header, func, period)

def save_resp(resp, fname, header="Downloading file...", func=print, period=0.5):
    pr = ProgressReporter(
        int(resp.headers.get("content-length", -1)), 
        header, 
        func, 
        period=period,
    )

    with open(fname, "wb") as f:
        for chunk in resp:
            f.write(chunk)
            pr(len(chunk))
