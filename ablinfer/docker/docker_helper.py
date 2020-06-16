"""Docker helper to simplify retrieving/sending single files."""

import os
import shutil
import tarfile

import docker

class _DLReader:
    """Wrapper to turn an iterator into a file object.

    This is for piping the result of a streaming `requests.get` into `tarfile`.
    """
    def read(self, count):
        buff = self.last
        while len(buff) < count:
            try:
                buff += next(self.it)
            except StopIteration:
                break
        if len(buff) > count:
            self.last = buff[count:]
            buff = buff[:count]
        else:
            self.last = bytes()

        self.offset += len(buff)

        return buff

    def seekable(self):
        return False

    def tell(self):
        return self.offset

    def seek(self, offset):
        todo = offset - self.offset
        if not todo:
            return
        elif todo < 0:
            raise ValueError("Can't seek backwards")

        buff = bytes()
        while todo > 0:
            try:
                buff = next(self.it)
            except StopIteration:
                break
            self.offset += len(buff)
            todo -= len(buff)
        if todo < 0:
            self.last = buff[todo:]

    def __init__(self, it):
        self.it = it
        self.last = bytes()
        self.offset = 0

class _SingleFileTar:
    """Quick-and-dirty tar creation implementation.

    Intended to avoid using a temporary archive file when the created archive just needs to be
    read as a file into some other function. Only works for regular files and doesn't store any
    metadata besides the filename.
    """
    def read(self, count):
        if self.offset == self.size:
            return b""

        while len(self.buff) < count:
            buff = self.fp.read(self.buffsize)
            self.buff += buff
            if len(buff) < self.buffsize: ## We've run out of file add the padding
                self.buff += b'\0'*(self.pad + 1024)
                break

        count = min(count, len(self.buff))

        if self.offset+count > self.size:
            print(self.offset, count, self.size)
            raise ValueError()
        self.offset += count
        ret = self.buff[:count]
        self.buff = self.buff[count:]

        return ret

    def close(self):
        self.fp.close()
        self.fp = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __iter__(self):
        assert self.offset == 0
        return self

    def __next__(self):
        buff = self.read(self.buffsize)

        if not buff:
            raise StopIteration

        return buff

    def __init__(self, fname, name=None, buffsize=2097152, mode=0o640):
        self.offset = 0
        self.fname = fname

        self.buffsize = buffsize

        self.fp = open(self.fname, "rb")

        ## Construct the header
        size = os.path.getsize(fname)

        header = bytes()

        pad = lambda i, s, p=b'\0': i + (p * max(s-len(i), 0))
        pad_num = lambda i, s, p='0': ((p*max(s-len(i)-1, 0)) + i).encode("ascii") + b'\0'

        ## File name
        header += pad((os.path.basename(fname) if name is None else name).encode("ascii")+b'\0', 100)
        ## File mode (ignore for now)
        header += pad_num(oct(mode)[2:][-3:], 8)
        ## File owner (numeric, as ASCII)
        header += pad_num("", 8)
        ## File group (numeric, as ASCII)
        header += pad_num("", 8)
        ## File size in bytes, as an octal string, padded with zeros
        header += pad_num(oct(size)[2:], 12)
        ## Modification time, Unix format, in octal
        header += pad(b"", 12)
        ## Checksum for header, MUST BE SPACES WHEN CALCULATING IT
        header += b' '*8
        ## File type
        header += b'\0'
        ## Link name
        header += pad(b"", 100)
        ## Ignore UStar fields, we don't care
        header = pad(header, 512)

        ## Calculate and replace the checksum
        checksum = sum(header)
        ## 6-digit octal number padded with zeros if necessary, plus a NUL and then a space (???)
        header = header[:148] + pad_num(oct(checksum)[2:], 6) + b"\0 " + header[156:]

        self.buff = header

        ## Total number of blocks: the header is one, plus the file padded to the nearest block,
        ## plus the final two empty blocks (so +3)
        blocks = (size + 511)//512 + 3

        if size%512:
            self.pad = 512 - size%512
        else:
            self.pad = 0

        self.size = blocks * 512

def put_file(
        container: docker.models.containers.Container, 
        path: str, 
        fname: str,
        name: str = None,
        mode: int = 0o640,
    ) ->  None:
    """Put a single file into a container.

    Only works on single regular files and ignores all metadata.

    :param path: The directory in the container to extract to.
    :param fname: The filename of the local file.
    :param name: The name to store in the tar file; defaults to the basename of the file.
    :param mode: The mode for the stored file (3-digit octal number).
    """

    with _SingleFileTar(fname, name, mode=mode) as f:
        container.put_archive(path, f)

def get_file(container: docker.models.containers.Container, path: str, dest: str = ".") ->  None:
    """Get a single file from a container.

    :param path: The path to retrieve.
    :param dest: The filename to extract to. If it is an existing directory, the filename from the
                 tar file will be used.
    """
    if os.path.isdir(dest):
        fname = None
    else:
        fname = dest

    it, _ = container.get_archive(path)
    reader = _DLReader(it)
    tf = tarfile.TarFile(mode="r", fileobj=reader)
    for member in tf:
        ## We only need the first one
        f = tf.extractfile(member)
        if fname is None:
            fname = os.path.join(dest, member.name)

        with open(fname, "wb") as of:
            shutil.copyfileobj(f, of)
