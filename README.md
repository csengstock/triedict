# triedict
A compressed python dictionary implemented as a Trie. Allows for lookup, prefix/predictive search, and Aho-Corasick string matching operations on the dictionary.

## About ##
A serializable Trie-based dictionary <TrieDict> for sequence-like objects
(strings, lists, tuples,...) that supports (1) lookup,
(2) prefix search - also called predictive search,
and (3) Aho-Corasick string matching.

Given the average length of the sequences is a constant `m` the
runtime complexities are:
* Lookup: O(m)
* Prefix search: O(m)
* Matching: O(t); t = length of the text

## Alpha Version ##
Currently only <unicode> or <str> keys and <int> values
are supported. Support for arbitrary key sequences
and values will follow.

## Objectives ##
In the following, the sequence-like keys of the dictionary
are called a 'patterns', and the items of the sequences
are called 'symbols'.

The objectives of the implementation can be summarized as:
(1) The triedict is memory-efficient by compressing the patterns
    on basis of their common prefixes, and by using native data-types (ctypes)
    to store the information.
(2) The triedict allows for fast serialization to disc.
(3) The triedict allows to implement the core logic in C routines
    by only using native C data-types within the Trie (not done yet).

## Usage ##
The native implementation allows as keys:
* Any sequence of <unicode>- or <str>-chars (e.g., strings or lists)

The native implementation allows as values:
* An <int>-type within the range [0,2**32-2]

To use other key- and value-types (next version feature):
* The user can provide a encoder function <object> -> <int> and a
  decoder function <int> -> <object> to transform the object symbols to
  integers and vice versa. The integers need be be in the range [0,2**32-1].
  Encoding and decoding happens inside the dictionary.
* The wrapper class <OTrieDict> allows to use any pickable object as values,
  on the cost of holding them in a list in memory.

Example usage with native data-types:

```
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
>>> print d.match("this is key1 and key2key1 in a string")
# [(11, "key1", 0), (19, "key2", 11), (23, "key1", 0)]
>>> print d.match("this is key1 and key2key1 in a string", bound_chars=" .,;!?'\"()[]$=")
# [(11, "key1", 0)]
```

## Internals ##

To achieve objectives:
* Small memory footprint - Usage of native data types (ctypes).
* Fast serialization - Trie nodes are kept in array to allow for fast binary
    serialization and de-serialization.
* Reasonable performance - Trie routines only use the native data types
    and the node-array. Allows for refactorization of the methods as
    c-routines (not yet done).

To allow for a fix-width node size (struct-size), the parent-children
relationship is modelled by a single child pointer and a brother pointer
(p_child, p_brother). Example Trie containing 'bus' and 'bugs':

```
 * (n0) -> 0  (root node)
 |
 b (n1) -> 0
 |
 u (n2) -> 0
 |
 s (n3) -> g (n4) -> 0
           |
           s (n5) -> 0
```

Corresponding nodes:

```
node[0]: symb  0x00,  p_child -> 0,  p_brother -> 0
node[1]: symb 'b',    p_child -> 2,  p_brother -> 0
node[2]: symb 'u',    p_child -> 3,  p_brother -> 0
node[3]: symb 's',    p_child -> 0,  p_brother -> 4
node[4]: symb 'g',    p_child -> 5,  p_brother -> 0
node[5]: symb 's',    p_child -> 0,  p_brother -> 0
```

Suffix pointers:
* To support Aho-Corasick string matching the nodes have a pointer
  to the node in the Trie, that represents its longest suffix (p_suffix pointer).
Node storage:
* The nodes are saved as structs in an array and the pointers are
  modelled as <uint32> indexes on that array. This allows for fast
  serialization without resolving the pointers. For the pointers
  (p_child, p_brother, p_suffix) a value of 0 corresponds to a null pointer.
