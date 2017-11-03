# Canonical XML Version 2.0 pure python implementation

A python port from java version located at:
    https://github.com/dept2/c14n2

Algorithm documentation page:
    https://www.w3.org/2008/xmlsec/Drafts/c14n-20/

Most of the test cases can be found on page:
    https://www.w3.org/2008/xmlsec/Drafts/c14n-20/test-cases/

# Feautures:
* no additional packeges needed
* supports canonization with or without comment removal
* supports canonization with or without prefix rewriting

# Installation:
```
    pip install https://github.com/dept2/c14n2py
```

# Example of usage:
```python
from xml.dom.minidom import parseString
from c14n2 import DOMCanonicalizer, Parameters

body = parseString("""
<a:foo xmlns:a="http://a" xmlns:b="http://b" xmlns:c="http://c">
 <b:bar/>
 <b:bar/>
 <b:bar/>
 <a:bar b:att1="val"/>
</a:foo>""")
params = Parameters()
params.trimTextNodes = True
params.prefixRewrite = Parameters.SEQUENTIAL
c14n_body = DOMCanonicalizer.canonicalize(body, params)
```
