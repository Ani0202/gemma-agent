import glob, sys
sp = glob.glob('/home/ubuntu/gemma-local/pyimg*/**/site-packages', recursive=True)
sys.path.extend(sp[:1])
import pytest
sys.exit(pytest.main(sys.argv[1:]))
