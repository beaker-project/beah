# -*- test-case-name: beah.misc.test.test_writers -*-

class Writer(object):

    # PUBLIC INTERFACE:

    def write(self, obj):
        self.send(self.repr(obj))

    def flush(self):
        pass

    def close(self):
        self.flush()

    # METHODS TO OVERRIDE:

    def repr(self, obj):
        """
        Data transformation function.

        This method should return obj's representation understood by receiver.
        """
        return obj

    def send(self, data):
        """
        Write data to receiver.
        """
        pass

class CachingWriter(Writer):

    """
    Writer class buffering data.

    It buffers data up to capacity length.
    If no_split is set, data submitted in one write won't be broken into more
    chunks.
    """

    def __init__(self, capacity=4096, no_split=False):
        self.capacity = capacity
        if no_split:
            self.quant = None
        else:
            self.quant = self.capacity
        self.buffer = ""

    def cache_append(self, data):
        self.buffer += data

    def cache_len(self):
        return len(self.buffer)

    def cache_get(self, length=None):
        if length is None or length >= len(self.buffer):
            return self.buffer
        else:
            return self.buffer[:length]

    def cache_pop(self, length):
        if length >= len(self.buffer):
            self.buffer = ""
        else:
            self.buffer = self.buffer[length:]

    def write_(self):
        while self.cache_len() >= self.capacity:
            data = self.cache_get(self.quant)
            self.send(data)
            self.cache_pop(len(data))

    def write(self, obj):
        self.cache_append(self.repr(obj))
        self.write_()

    def flush(self):
        if self.cache_len() > 0:
            data = self.cache_get()
            self.send(data)
            self.cache_pop(len(data))

class JournallingWriter(CachingWriter):

    """
    Writer saving all data to a journal.

    Subclass should override set_offset to write to persistent location.
    """

    def __init__(self, journal, offset=-1, capacity=4096, no_split=False):
        """
        journal: file-like object.
        offset: position of data which were not sent. -1 - EOF.
        """
        self.journal = journal
        if offset < 0:
            self.journal.seek(0, 2)
            self.set_offset(self.journal.tell())
            unflushed_cache = ""
        else:
            self.set_offset(offset)
            self.journal.seek(offset)
            unflushed_cache = self.journal.read()
        CachingWriter.__init__(self, capacity=capacity, no_split=no_split)
        if unflushed_cache:
            CachingWriter.cache_append(self, unflushed_cache)
            self.write_()

    def cache_append(self, data):
        self.journal.write(data)
        CachingWriter.cache_append(self, data)

    def cache_pop(self, length):
        self.set_offset(self.get_offset()+length)
        CachingWriter.cache_pop(self, length)

    def set_offset(self, offset):
        self._offset = offset

    def get_offset(self):
        return self._offset

