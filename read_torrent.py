import hashlib


# ---------------------------------------------------
# Simple Bencode Decoder
# ---------------------------------------------------

def bdecode(data):
    def decode_next(index):
        if data[index:index+1] == b'i':
            end = data.index(b'e', index)
            number = int(data[index+1:end])
            return number, end + 1

        elif data[index:index+1] == b'l':
            index += 1
            lst = []
            while data[index:index+1] != b'e':
                item, index = decode_next(index)
                lst.append(item)
            return lst, index + 1

        elif data[index:index+1] == b'd':
            index += 1
            dct = {}
            while data[index:index+1] != b'e':
                key, index = decode_next(index)
                value, index = decode_next(index)
                dct[key] = value
            return dct, index + 1

        elif data[index:index+1].isdigit():
            colon = data.index(b':', index)
            length = int(data[index:colon])
            start = colon + 1
            end = start + length
            return data[start:end], end

        else:
            raise ValueError("Invalid bencode format")

    decoded, _ = decode_next(0)
    return decoded


# ---------------------------------------------------
# Torrent Reader
# ---------------------------------------------------

class TorrentFile:
    def __init__(self, filepath):
        with open(filepath, "rb") as f:
            self.raw_data = f.read()

        self.meta = bdecode(self.raw_data)

        self.announce = self.meta.get(b'announce', b'').decode()
        self.info = self.meta[b'info']

        # Compute info_hash (SHA1 of bencoded info dict)
        self.info_hash = hashlib.sha1(self._bencode(self.info)).hexdigest()

        self.name = self.info.get(b'name', b'').decode()
        self.piece_length = self.info.get(b'piece length')
        self.pieces = self.info.get(b'pieces')

        if b'length' in self.info:
            self.length = self.info[b'length']
            self.files = None
        else:
            self.length = None
            self.files = self.info.get(b'files')

    # Minimal bencode encoder (needed to compute info_hash)
    def _bencode(self, obj):
        if isinstance(obj, int):
            return b'i' + str(obj).encode() + b'e'
        elif isinstance(obj, bytes):
            return str(len(obj)).encode() + b':' + obj
        elif isinstance(obj, list):
            return b'l' + b''.join(self._bencode(x) for x in obj) + b'e'
        elif isinstance(obj, dict):
            result = b'd'
            for key in sorted(obj.keys()):
                result += self._bencode(key)
                result += self._bencode(obj[key])
            result += b'e'
            return result
        else:
            raise TypeError("Unsupported type")

    def print_summary(self):
        print("\n--- Torrent Info ---")
        print("Announce URL:", self.announce)
        print("Name:", self.name)
        print("Piece length:", self.piece_length)
        print("Info hash:", self.info_hash)

        if self.length:
            print("File size:", self.length)
        elif self.files:
            print("Multi-file torrent:")
            for f in self.files:
                print(" -", b"/".join(f[b'path']).decode(), "(", f[b'length'], "bytes )")
