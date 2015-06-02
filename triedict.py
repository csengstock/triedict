# triedict
#
# Copyright (c) 2015 Christian Sengstock, All rights reserved.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3.0 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.

"""
# triedict #

A compressed and serializable python dictionary implemented as a Trie.
Allows for
(1) lookup,
(2) prefix search - also called predictive search, and 
(3) Aho-Corasick string matching
of sequece-like keys.

Given the average length of the sequences is a constant `m` the
runtime complexities are:
* Lookup: O(m)
* Prefix search: O(m)
* Matching: O(t); t = length of the text

## Alpha Version ##
Currently only <unicode> or <str> keys and <int> values
are supported. Support for arbitrary key sequences
and values will follow.

## Usage ##
>>> from triedict import TrieDict
>>> d = TrieDict()
>>> d["key1"] = 0
>>> d["key2"] = 1
>>> d["key2"] = 11
>>> print "key1" in d  # True
>>> print "key2" in d  # True
>>> print "key3" in d  # False
>>> print d["key1"]    # 0
>>> print d["key2"]    # 11
>>> print d["key3"]    # None
>>> print d.lookup("key1")  # 0
>>> print d.lookup("key2")  # 11
>>> print d.lookup("key3")  # None
>>> print d.prefix_search("ke")  # [("y1",0), ("y2",11)]
>>> d.generate_prefix_pointers()
>>> print d.match("this is key1 and key2key1 in a string")
# [(11, "key1", 0), (19, "key2", 11), (23, "key1", 0)]
>>> print d.match("this is key1 and key2key1 in a string", bound_chars=" .,;!?'\"()[]$=")
# [(11, "key1", 0)]

## Internals ##
see README.md
"""

import sys
from ctypes import Structure, c_uint32, c_bool, sizeof, \
     POINTER, resize, memset, create_string_buffer, byref
from collections import deque

DEF_BOUND_CHARS = " !?=-*+#:;,.'\"()&%$"

class Header(Structure):
    """
    Holds essential dictionary information.
    This is stored as the first bytes of the
    serialized Trie.
    """
    _fields_ = [("n_nodes", c_uint32),
                ("n_patterns", c_uint32),
                ("has_suffix_pointers", c_bool)]

class Node(Structure):
    """
    Fix-width node of the Trie.
    """
    _fields_ = [("symbol",    c_uint32),
                ("value",     c_uint32),
                ("p_brother", c_uint32),
                ("p_child",   c_uint32),
                ("p_suffix",  c_uint32),
                ("p_parent",  c_uint32)]

    def is_root(self):
        return self.symbol == 0

    def is_pattern(self):
        """
        Returns True if this node is the
        end-node of a pattern in the dictionary.
        """
        return self.value != 0

    def __repr__(self):
        return "Node(symb: %s, brother: %d, child: %d, parent: %d, suffix: %d, value: %d)" \
               % (self.symbol, self.p_brother, self.p_child, self.p_parent, self.p_suffix, self.value)


class TrieDict(object):
    """
    Trie-based dictionary.
    """

    # This pointer type is used to point to the nodes
    # in the array. Gets instantiated after each #resize(.)
    # call on the array.
    _P = POINTER(Node)
    _MAX_PATTERN_ID = 2**32-2

    def __init__(self, init_n=1, symbol_encoder=None, symbol_decoder=None):
        """
        Constructs a new dictionary.

        Args:
            init_n: Inital number of buffer nodes (size of
                the underlying array).
            symbol_encoder: A function <object> -> <int>
            symbol_decoder: A function <int> -> <object>
        """

        # set the en/de-coder and fall back to unicode characters
        self._symbol_encoder = symbol_encoder
        if not self._symbol_encoder:
            self._symbol_encoder = ord
        self._symbol_decoder = symbol_decoder
        if not self._symbol_decoder:
            self._symbol_decoder = unichr

        self._header = Header()
        self._header.n_nodes = 1
        self._header.n_patterns = 0
        self._header.has_suffix_pointers = False

        # node array
        self._data = (Node * init_n)()

        # pointer to node array
        self._p = TrieDict._P(self._data)

        # number of nodes fitting in memory
        self._buf_nodes = init_n

    # INTERFACE ///////////////////////////////////////////////////////////

    @staticmethod
    def load(fn):
        """
        Loads the dictionary from disc.

        Args:
            fn: The filename of the file.
        """
        fp = open(fn, "rb")
        header = Header()
        fp.readinto(header)
        data = create_string_buffer(header.n_nodes*sizeof(Node))
        fp.readinto(data)
        fp.close()

        triedict = TrieDict(1)
        triedict._header = header
        triedict._data = data
        triedict._p = TrieDict._P(triedict._data)
        triedict._buf_nodes = triedict._header.n_nodes

        return triedict

    def save(self, fn):
        """
        Serializes the dictionary to file [fn].

        Args:
            fn: The filename of the file.
        """
        resize(self._data, self._header.n_nodes * sizeof(Node))
        fp = open(fn, "wb")
        fp.write(self._header)
        fp.write(self._data)
        fp.close()

    def has_suffix_pointers(self):
        """
        Returns True if the suffix pointers have
        been generated, else, False.
        """
        return self._header.has_suffix_pointers

    def size(self):
        """
        Number of patterns (sequences) stored in the dictionary.
        """
        return self._header.n_patterns

    def num_of_nodes(self):
        """
        Number of nodes in the dictionary.
        The available number of nodes might be
        larger. See #num_of_buf_nodes()
        """
        return self._header.n_nodes

    def num_of_buf_nodes(self):
        """
        Number of internal buffer nodes (array size).
        The memory usage of the dictionary can be computed
        as:

        #num_of_buf_nodes() * sizeof(Node)
        """
        return self._buf_nodes

    def add_pattern(self, s, patternID=1):
        """
        Adds a new pattern to the dictionary.
        The pattern can be found using #lookup(s)
        #prefix_search(s) and #match(t), where t is
        any sequence of symbols.

        Args:
            s: A pattern (sequence) of symbols. The symbols
              are transformed into unsigned integers using the
              symbol_encoder function (see constructor;
              defaults to 'ord').

            patternID: Integer in range [0,2**32-2]. This can
              be used to establish a link to an underlying object
              (e.g., an index to a list of strings, etc.).

              If no patternID is not provided, the ID defaults
              to 1, indicating a matching pattern in the dictionary.
        """
        if (patternID < 0) or (patternID > TrieDict._MAX_PATTERN_ID):
            raise ValueError("patternID must be in range [0,2**32-2]!")

        patternID += 1

        ni = 0
        nd = self._getnode(ni) # current node object (root)

        new_pattern = False
        for symbol in s:
            c = self._symbol_encoder(symbol)
            if c == 0:
                raise ValueError("encoded symbol should not have value 0!")
            if nd.p_child == 0:
                # Node has no child yet;
                # create new child node
                nni, nnd = self._create_new_node(c, ni)
                new_pattern = True
                # The pointer _p might have changed
                # when the array was increased (since the increase
                # can move the arrays' memory block).
                # Since the nodes are aware of the pointer
                # by which they have been retrieved,
                # we need to get the node once again after a
                # create_new_node() call.
                nd = self._getnode(ni)

                # now make the new node the current node
                nd.p_child = nni
                nd = nnd
                ni = nni
                continue
            else:
                # follow the linked list starting with
                # the child to find matching node
                parent_ni = ni
                ni = nd.p_child
                nd = self._getnode(ni)
                while nd.p_brother != 0 and nd.symbol != c:
                    ni = nd.p_brother
                    nd = self._getnode(ni)
                if nd.symbol != c:
                    # no matching node has been found;
                    # create new brother node
                    nni, nnd = self._create_new_node(c, parent_ni)
                    new_pattern = True
                    nd = self._getnode(ni)
                    nd.p_brother = nni
                    nd = nnd
                    ni = nni
        nd.value = patternID
        if new_pattern:
            self._header.n_patterns += 1

    def lookup(self, s):
        """
        see #get(s)
        """
        return self.get(s)

    def get(self, s):
        """
        Returns the value of the pattern s
        or None, if the pattern is not stored
        in the dictionary.
        """

        ni = self._get_pattern_node(s)
        if ni != 0:
            nd = self._p[ni]
            if nd.value != 0:
                return nd.value - 1
        return None

    def prefix_search(self, prefix, join_patterns=True):
        """
        Returns the suffixes of the patterns that start with
        prefix.

        Args:
            prefix: The prefix pattern (sequence)
            joined_suffix: If True, the decoded symbols
               in the suffix sequences are joined to a string.
               Else, the symbols are returned as a list object.

        Returns:
            A list of (suffix-sequence, value) tuples.
        """

        ni = self._get_pattern_node(prefix)
        res = []
        if ni != 0:
            self._collect_subtree_links(ni, res)

        self._decode_pattern_result(res, join_patterns)
        return res

    def match(self, s, join_patterns=True, bound_chars=None):
        return self.parse(s, join_patterns, bound_chars)

    def parse(self, s, join_patterns=True, bound_chars=None):
        """
        Finds all stored patterns that occur in the string s
        in approximately O(len(s)) time.

        Args:
            s:  A string or sequence-like object.

        Returns.
            A list of (value, pos) tuples.
        """


        if not self._header.has_suffix_pointers:
            raise ValueError("Trie has no suffix pointers!")

        matched = []
        ni = 0
        nd = self._p[ni]
        pos = 0
        m = len(s)
        while pos < m:
            c = self._symbol_encoder(s[pos])

            child_ni, child_nd = self._get_matching_child(nd, c)

            if child_ni == None:
                if nd.is_root():
                    pos += 1
                else:
                    ni = nd.p_suffix
                    nd = self._p[ni]
                continue

            ni = child_ni
            nd = child_nd

            suff_path_ni = ni
            suff_path_nd = self._p[suff_path_ni]
            while not suff_path_nd.is_root():
                if suff_path_nd.is_pattern():
                    matched.append((self._get_path(suff_path_ni), suff_path_nd.value, pos))
                suff_path_ni = suff_path_nd.p_suffix
                suff_path_nd = self._p[suff_path_ni]
            pos += 1

        self._decode_pattern_result(matched, join_patterns)
        if bound_chars:
            TrieDict._remove_matches_without_bounds(s, matched, bound_chars)
        return matched

    def generate_suffix_pointers(self, verbose=True):
        self.generate_suffix_links(verbose)

    def generate_suffix_links(self, verbose=True):
        """
        Generates the suffix pointers in the Trie.
        Those are needed for the #parse() method.
        """

        nd = self._p[0]
        if nd.p_child == 0:
            raise ValueError("empty trie!")

        # fill queue with roots' child nodes
        queue = deque()
        child_ni = nd.p_child
        cnt = 1
        while child_ni != 0:
            queue.append(child_ni)
            child_ni = self._p[child_ni].p_brother
            cnt += 1

        while len(queue) > 0:
            if verbose and cnt % 1000 == 0:
                sys.stderr.write("\r%.2f%%" % (float(cnt)/self._header.n_nodes)*100)
                sys.stderr.flush()
            # Check if the children of this node match
            # the children of one of the nodes
            # along the suffix path (including root);
            # In case of a match the
            # node along the suffix path becomes
            # the suffix node of the child node.

            # get current node
            ni = queue.popleft()
            nd = self._p[ni]

            # find suffix nodes of all childs
            child_ni = nd.p_child
            while child_ni != 0:
                child_nd = self._p[child_ni]

                cnt += 1 # debug counter

                # Go down the suffix path and check
                # if a child of the suffix path node matches
                # the current child node. If yes, make this node
                # the suffix node of the current child node.
                # We know child_nd is not root, so
                # we can always access the suffix of
                # the current child node.
                # (which might be root)

                path_nd = nd
                while not path_nd.is_root(): # root node check
                    path_suffix_nd = self._p[path_nd.p_suffix]
                    path_suffix_child_ni = path_suffix_nd.p_child
                    while path_suffix_child_ni != 0:
                        path_suffix_child_nd = self._p[path_suffix_child_ni]
                        if path_suffix_child_nd.symbol == child_nd.symbol:
                            child_nd.p_suffix = path_suffix_child_ni
                            break
                        path_suffix_child_ni = path_suffix_child_nd.p_brother
                    if path_suffix_child_ni != 0:
                        break
                    path_nd = self._p[path_nd.p_suffix]

                if child_nd.p_child != 0:
                    queue.append(child_ni)

                # go to the next child of the current nd.
                child_ni = child_nd.p_brother

        if verbose:
            sys.stderr.write("\n")
        self._header.has_suffix_pointers = True

    # OBJECT OVERWRITES /////////////////////////////////////////////////////////

    def __len__(self):
        """
        Number of patterns (sequences) stored in the dictionary.
        """
        return self._header.n_patterns

    def __repr__(self):
        return "TrieDict(patterns/size: %d, nodes: %d, buffer: %d, has_suffix_pointers: %d)" % \
               (self.size(), self.num_of_nodes(), self.num_of_buf_nodes(), self.has_suffix_pointers())

    def __delitem__(self, key):
        raise NotImplementedError("del not supported")

    def __setitem__(self, key, value):
        self.add_pattern(key, value)

    def __getitem__(self, key):
        value = self.lookup(key)
        if value == None:
            raise ValueError("key not in dictionary")

    def __contains__(self, key):
        value = self.lookup(key)
        return value != 0

    # HELPERS /////////////////////////////////////////////////////////

    def _to_string(self):
        """
        Returns a string representation of the Trie.
        """

        if self._header.n_nodes > 500:
            return "[[to many nodes]]"
        N = self._p
        out = []
        stack = [(0,0)]
        while len(stack) > 0:
            ni, depth = stack.pop()
            nd = N[ni]
            sout = "%s %d %s %s" % ("+"*depth, ni, self._symbol_decoder(nd.symbol), str(nd))
            out.append(sout)

            child_ni = nd.p_child
            while child_ni != 0:
                stack.append( (child_ni, depth+1) )
                child_ni = N[child_ni].p_brother
        return "\n".join(out)

    def _get_path(self, ni):
        path = []
        nd = self._getnode(ni)
        nd_start = nd
        while nd.symbol != 0:
            path.append(nd.symbol)
            nd = self._getnode(nd.p_parent)
        path.reverse()
        #print path, nd_start
        return path

    def _get_pattern_node(self, s):
        """
        Returns the nodeIdx of the node
        ending at s[-1], or 0 if
        pattern s does not exist.
        """
        ni = 0
        nd = self._p[ni]
        for symbol in s:
            c = self._symbol_encoder(symbol)
            if nd.p_child != 0:
                ni = nd.p_child
                nd = self._p[ni]
                while nd.p_brother != 0 and nd.symbol != c:
                    ni = nd.p_brother
                    nd = self._p[ni]
                if nd.symbol != c:
                    return 0
            else:
                return 0
        return ni

    def _get_matching_child(self, nd, symbol):
        """
        Returns a (nodeIdx, node) tuple of
        that child node of [nd], that matches
        [symbol], otherwise (None, None).
        """
        child_ni = nd.p_child
        while child_ni != 0:
            child_nd = self._p[child_ni]
            if child_nd.symbol == symbol:
                return child_ni, child_nd
            child_ni = child_nd.p_brother
        return None, None

    def _collect_subtree_links(self, ni, res):
        # Explicit recursion using a stack.
        # Needs to differentiate when a node has been
        # added (state=0) and when it is to be removed
        # (state=1) to update the current path accordingly.

        #    (state, nodeIdx)
        stack = [(0, ni)]
        path = []
        while len(stack) > 0:
            state, ni = stack.pop()
            if state == 1:
                path.pop()
            else:
                stack.append((1, ni))
                nd = self._p[ni]
                path.append(nd.symbol)
                if nd.value != 0:
                    res.append((path[1:], nd.value))
                child_ni = nd.p_child
                while child_ni != 0:
                    stack.append((0, child_ni))
                    child_ni = self._p[child_ni].p_brother

    def _increase_mem(self):
        """
        Doubles the size of the node array.
        The size must be increased on the _data
        member, since this ctype object owns the memory.
        """

        s_bytes = self._buf_nodes * sizeof(Node)
        if s_bytes != sizeof(self._data):
            raise ValueError("Internal Error!")

        resize(self._data, s_bytes*2)
        memset(byref(self._data, s_bytes), 0, s_bytes)

        self._buf_nodes *= 2
        # Renew the pointer since the arrays' memory
        # might have been moved.
        self._p = TrieDict._P(self._data)

    def _create_new_node(self, symbol, parent_ni):
        if self._header.n_nodes >= self._buf_nodes:
            self._increase_mem()
        ni = self._header.n_nodes
        self._header.n_nodes += 1
        nd = self._getnode(ni)
        nd.symbol = symbol
        nd.p_parent = parent_ni
        return ni, nd

    def _getnode(self, ni):
        return self._p[ni]

    def _decode_pattern_result(self, res, join_patterns):
        for j in xrange(len(res)):
            suffix = res[j][0]
            for i in xrange(len(suffix)):
                suffix[i] = self._symbol_decoder(suffix[i])
            if join_patterns:
                suffix = "".join(suffix)
            res[j] = (suffix, res[j][1]-1) + res[j][2:]

    @staticmethod
    def _remove_matches_without_bounds(s, res, bound_chars):
        bound_chars = set(bound_chars)
        m = len(s)
        for i in xrange(len(res)-1, -1, -1):
            n = len(res[i][0])
            end_pos = res[i][2]
            start_pos = end_pos+1-n
            if not ((start_pos == 0 or s[start_pos-1] in bound_chars) and \
                    (end_pos == m-1 or s[end_pos+1] in bound_chars)):
                del res[i]


if __name__ == "__main__":
    #from triedict import TrieDict
    d = TrieDict()
    d["key1"] = 0
    d["key2"] = 1
    d["key2"] = 11
    print "key1" in d  # True
    print "key2" in d  # True
    print "key3" in d  # False
    print d["key1"]    # 0
    print d["key2"]    # 11
    try:
        print d["key3"]    # exception
    except ValueError, e:
        print e
    print d.lookup("key1")  # 0
    print d.lookup("key2")  # 11
    print d.lookup("key3")  # None
    print d.prefix_search("ke")  # [("y1",0), ("y2",11)]
    d.generate_suffix_pointers()
    print d.match("this is key1 and key2key1 in a string")
    #    key   val pos
    # [("key1", 0, 11), ("key2", 11, 20), ("key1", 0, 24)]
    print d.match("this is key1 and key2key1 in a string", bound_chars=" .,;!?'\"()[]$=")
    #    key, val, pos
    # [("key1", 0, 11)]
