"""Read-only evidence for the bounded current-server tactical profiles.

Requires local pefile and capstone. Prints review data; never writes or loads
the game DLL. Direct dependencies are one level, not a claimed engine closure.
"""
from __future__ import annotations

import hashlib
import json
import sys

import capstone
import pefile


def report(path: str) -> dict:
    pe = pefile.PE(path)
    image = pe.get_memory_mapped_image()
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    ranges = [(row.struct.BeginAddress, row.struct.EndAddress)
              for row in pe.DIRECTORY_ENTRY_EXCEPTION]

    complete_known = {0x2dda40: 347, 0x2fc1d0: 20, 0x2e6d30: 1500}

    def function(rva: int) -> tuple[int, int]:
        if rva in complete_known:
            return rva, rva + complete_known[rva]
        found = next(((start, end) for start, end in ranges if start <= rva < end), None)
        if found:
            if found[0] != rva:
                raise ValueError(f"Target is inside a function: {rva:x} {found}")
            return found
        # Leaf wrappers have no unwind entry. Their RET/tail-JMP followed by
        # alignment padding supplies a bounded complete body, for review below.
        for ins in md.disasm(image[rva:rva + 1024], rva):
            end = ins.address + ins.size
            if ins.mnemonic in ("ret", "jmp") and image[end:end + 1] == b"\xcc":
                return rva, end
        raise ValueError(f"No bounded leaf function at {rva:x}")

    nav = [(0x2bafa0, 1758), (0x32a630, 151), (0x32aaf0, 33),
           (0x2de010, 275), (0x2dd880, 173), (0x330e90, 3133),
           (0x2cce50, 131), (0x2cdc90, 46), (0x2cb9a0, 153),
           (0x2cfec0, 39), (0x2c8230, 29), (0x2dcab0, 8), (0x2e7a00, 93)]
    look = [(0x2dda40, 347), (0x2fc1d0, 20), (0x2e6d30, 1500)]
    constructor = next((start, end - start) for start, end in ranges if start <= 0x2af23d < end)

    def feature(seeds: list[tuple[int, int]], observation: bool) -> dict:
        direct = set()
        constants = set()
        for rva, size in seeds:
            for ins in md.disasm(image[rva:rva + size], rva):
                if ins.mnemonic in ("call", "jmp") and ins.operands[0].type == capstone.CS_OP_IMM:
                    target = ins.operands[0].imm
                    if not any(start <= target < start + count for start, count in seeds):
                        direct.add(target)
                for operand in ins.operands:
                    if operand.type == capstone.CS_OP_MEM and operand.mem.base == capstone.x86.X86_REG_RIP:
                        target = ins.address + ins.size + operand.mem.disp
                        section = next(s for s in pe.sections
                                       if s.VirtualAddress <= target < s.VirtualAddress + s.Misc_VirtualSize)
                        if section.Name.rstrip(b"\x00") == b".rdata":
                            constants.add((target, max(operand.size, 8)))
        # SetState's state callbacks and low CCSBot virtual methods are direct
        # dependencies too. Pin code behind the already-reviewed slots, not
        # only the table's pointer. Other engine object virtual dispatch is
        # outside this bounded tactical profile, as before.
        slots = [0x17ad970 + offset for offset in
                 ([0x18, 0x40, 0x48, 0x50, 0x58, 0x60, 0x68, 0x70] if observation else
                  [0x18, 0x28, 0x30, 0x40, 0x48, 0x50, 0x58, 0x60, 0x68, 0x70])]
        if not observation:
            for table in (0x17ad728, 0x17ad758, 0x17ad788, 0x17ad7b8, 0x17ad7e8,
                          0x17ad820, 0x17ad858, 0x17ad890, 0x17ad8c8, 0x17ad900, 0x17ad938):
                slots.extend(table + offset for offset in (0, 8, 16, 24))
        for slot in slots:
            target = int.from_bytes(image[slot:slot + 8], 'little') - pe.OPTIONAL_HEADER.ImageBase
            start, end = function(target)
            direct.add(start)
        bodies = list(seeds) + [constructor]
        for target in sorted(direct):
            start, end = function(target)
            bodies.append((start, end - start))
        # Some Windows unwind entries split one logical function (SetLookAt
        # above is a reviewed example). Pin any additional intra-function
        # branch chunk too. This does not recurse into helper callees.
        index = 0
        while index < len(bodies):
            rva, size = bodies[index]
            index += 1
            for ins in md.disasm(image[rva:rva + size], rva):
                if (ins.group(capstone.CS_GRP_JUMP) and ins.operands[0].type == capstone.CS_OP_IMM
                        and ins.mnemonic != "jmp"):
                    target = ins.operands[0].imm
                    if any(start <= target < start + count for start, count in bodies):
                        continue
                    found = next(((start, end) for start, end in ranges if start <= target < end), None)
                    if found:
                        bodies.append((found[0], found[1] - found[0]))
                    else:
                        raise ValueError(f"Unbounded function branch chunk: {target:x}")
        return {
            "bodies": [{"rva": rva, "length": size,
                        "sha": hashlib.sha256(image[rva:rva + size]).hexdigest().upper()}
                       for rva, size in sorted(set(bodies))],
            "constants": sorted(constants),
            "virtual_slots": slots,
        }

    return {
        "server_sha": hashlib.sha256(pe.__data__).hexdigest().upper(),
        "image_base": pe.OPTIONAL_HEADER.ImageBase,
        "image_size": pe.OPTIONAL_HEADER.SizeOfImage,
        "sections": [{"name": s.Name.rstrip(b"\x00").decode(),
                      "rva": s.VirtualAddress, "virtual_size": s.Misc_VirtualSize,
                      "raw": s.PointerToRawData, "raw_size": s.SizeOfRawData,
                      "characteristics": s.Characteristics,
                      "sha": hashlib.sha256(s.get_data()).hexdigest().upper()}
                     for s in pe.sections],
        "directories": [(d.VirtualAddress, d.Size) for d in pe.OPTIONAL_HEADER.DATA_DIRECTORY],
        "navigation": feature(nav, False),
        "observation": feature(look, True),
    }


if __name__ == "__main__":
    print(json.dumps(report(sys.argv[1]), indent=2))
