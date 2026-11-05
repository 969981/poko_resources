#!/usr/bin/env python3
"""Verify original 2.0.1 Pokemon texture objects from KIDSOBJDB bytes.

Original IDOK scalar fields contain G1T and TEXINFO resource hashes, NOT an
observed native Pokedex ID. Keep the species-ID column unverified.
"""
import csv,hashlib,json,struct
from collections import Counter
from pathlib import Path

ROOT=Path("UnPack/2.0.1/Resources")
PACK=Path("UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0xacd220a8.fdata/native")
SOURCES={
  "0xacd220a8__50ae86ef.kidsobjdb":PACK/"root_019167_50ae86ef.kidsobjdb",
  "0xacd220a8__e2e43333.kidsobjdb":PACK/"root_053829_e2e43333.kidsobjdb"}
G1T=0xc8bb66da
TEXINFO=0x2276fc56
UNKNOWN=0x2856a1b3
TYPE=0x79991e79
WIDTHS={0:1,1:1,2:2,3:2,4:4,5:4,6:8,7:8,8:4,10:16,12:8,13:12}
COLS=("texture_name","texture_category","candidate_texture_number",
      "native_species_id_verified","object_hash","objdb_file",
      "source_file_sha256","node_index","node_byte_offset","node_type_hash",
      "g1t_hash","texinfo_hash","g1t_value_offset","texinfo_value_offset",
      "third_value_offset","third_raw_u32","verification_status")

def u(b,p):return struct.unpack_from("<I",b,p)[0]
def hx(x):return f"{x:08x}"

def parse_kids(blob):
    if len(blob)<28 or blob[:8]!=b"_DOK0000" or (u(blob,8),u(blob,12))!=(28,24) or u(blob,24)!=len(blob):
        raise ValueError("Invalid original _DOK0000 header/size")
    count=u(blob,16)
    if count>1000000:raise ValueError("Unsafe original IDOK node count")
    result={}
    pos=28
    for index in range(count):
        if pos+24>len(blob) or blob[pos:pos+8]!=b"IDOK0000":
            raise ValueError(f"Invalid original IDOK at {pos}")
        size,oid,typ,n=(u(blob,pos+k) for k in (8,12,16,20))
        end=pos+size
        if size<24 or end>len(blob) or n>4096 or pos+24+12*n>end:
            raise ValueError("Invalid IDOK length/descriptor table")
        at=pos+24+n*12
        fields={}
        for i in range(n):
            q=pos+24+i*12
            t,num,name=(u(blob,q+k) for k in (0,4,8))
            if t not in WIDTHS or num*WIDTHS[t]>end-at or name in fields:
                raise ValueError("Invalid original typed property")
            fields[name]={"kind":t,"count":num,"offset":at,
                          "u32":u(blob,at) if t in (4,5) and num==1 else None}
            at+=num*WIDTHS[t]
        if at!=end:raise ValueError("Unconsumed native IDOK payload")
        if oid in result:raise ValueError("Duplicate native object ID")
        result[oid]={"index":index,"offset":pos,"type":typ,"fields":fields}
        nextpos=(end+3)&~3
        if nextpos>len(blob) or any(blob[end:nextpos]):
            raise ValueError("Invalid IDOK alignment padding")
        pos=nextpos
    if pos!=len(blob):raise ValueError("Native node count/size mismatch")
    return {"nodes":count,"source_sha256":hashlib.sha256(blob).hexdigest(),
            "name_resource_hash":hx(u(blob,20))},result

def verify(crosswalk,binaries):
    db={name:parse_kids(binaries[name]) for name in SOURCES}
    counter=Counter();third=Counter();rows=[]
    for sprite in crosswalk:
        name=sprite["objdb_file"]
        if name not in db:raise ValueError("Unexpected native texture object origin")
        info,nodes=db[name]
        oid=int(sprite["object_hash"],16)
        if oid not in nodes:raise ValueError("Missing original object hash")
        obj=nodes[oid]
        props=obj["fields"]
        if obj["type"]!=TYPE or set(props)!={G1T,TEXINFO,UNKNOWN} or any(
            p["kind"]!=5 or p["count"]!=1 for p in props.values()
        ):raise ValueError("Incorrect original native G1T/TEXINFO property layout")
        if (hx(props[G1T]["u32"])!=sprite["g1t_hash"] or
            hx(props[TEXINFO]["u32"])!=sprite["texinfo_hash"]):
            raise ValueError("Native bytes contradict original sprite hash index")
        if sprite["native_species_id_verified"]:
            raise ValueError("Refuse unsourced species-ID field")
        counter[name]+=1
        third[hx(props[UNKNOWN]["u32"])]+=1
        rows.append(dict(texture_name=sprite["texture_name"],
            texture_category=sprite["texture_category"],
            candidate_texture_number=sprite["texture_number_candidate"],
            native_species_id_verified="",object_hash=sprite["object_hash"],
            objdb_file=name,source_file_sha256=info["source_sha256"],
            node_index=obj["index"],node_byte_offset=obj["offset"],
            node_type_hash=hx(obj["type"]),g1t_hash=sprite["g1t_hash"],
            texinfo_hash=sprite["texinfo_hash"],
            g1t_value_offset=props[G1T]["offset"],
            texinfo_value_offset=props[TEXINFO]["offset"],
            third_value_offset=props[UNKNOWN]["offset"],
            third_raw_u32=hx(props[UNKNOWN]["u32"]),
            verification_status="NATIVE_SCALAR_G1T_TEXINFO_HASH_VALUES_MATCH__SPECIES_UNVERIFIED"))
    if len(rows)!=609 or dict(counter)!={"0xacd220a8__50ae86ef.kidsobjdb":608,
                                           "0xacd220a8__e2e43333.kidsobjdb":1}:
        raise ValueError("Original Pokémon texture source coverage changed")
    report={"status":"609_NATIVE_TEXTURE_HASH_BINDINGS_EXACT",
        "source_databases":[{"name":name,**db[name][0]} for name in SOURCES],
        "matched_records":len(rows),"matched_by_database":dict(counter),
        "native_layout_object_type_hash":hx(TYPE),
        "native_field_hashes":{"g1t":hx(G1T),"texinfo":hx(TEXINFO),
                               "third_unknown":hx(UNKNOWN)},
        "third_raw_value_histogram":dict(third),
        "species_id_bindings_verified":0,
        "out_of_scope_ui_texture":"icon_poke_at_home",
        "next_required_proof":"A native species/form table or runtime consumer referencing this layout object hash and passing a proven species ID",
        "warning":"Exact G1T/TEXINFO resource pointers are verified, not original Pokémon species IDs."}
    return rows,report

def main():
    with (ROOT/"Pokemon/pokemon_identity_crosswalk.csv").open(encoding="utf-8",newline="") as f:
        source=list(csv.DictReader(f))
    original={name:path.read_bytes() for name,path in SOURCES.items()}
    rows,report=verify(source,original)
    out=ROOT/"Pokemon/NativeCallers/M16"
    out.mkdir(parents=True,exist_ok=True)
    with (out/"pokemon_original_kidsobjdb_layout_bindings.csv").open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=COLS);writer.writeheader();writer.writerows(rows)
    (out/"m16_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
