import sys, pefile, capstone
exe, out = sys.argv[1], sys.argv[2]
pe = pefile.PE(exe, fast_load=True)
base = pe.OPTIONAL_HEADER.ImageBase
data = open(exe,'rb').read()
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
md.skipdata = True
with open(out,'w',encoding='utf-8') as f:
    for s in pe.sections:
        name = s.Name.rstrip(b'\0').decode()
        if not (s.Characteristics & 0x20000000): continue
        off, size, va = s.PointerToRawData, s.Misc_VirtualSize, base + s.VirtualAddress
        code = data[off:off+size]
        for ins in md.disasm(code, va):
            f.write(f"{ins.address:08x}  {ins.bytes.hex():<20} {ins.mnemonic} {ins.op_str}\n")
