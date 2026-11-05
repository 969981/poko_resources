-- Pokopia 2.0.1 M9 reference graph (SQLite)
-- Item/MapPart/Role edges are verified using original field layouts.
-- KIDSOBJDB numeric candidates are deliberately NOT foreign keys.

-- Confirmed consumers of a native table row (table 4645, example row 520).
SELECT edge_id, source_domain, source_record_id, source_entry,
       source_field_offset, target_group_start, target_text_id,
       category, evidence_grade, intermediates
FROM verified_edges
WHERE target_group_start = 4645 AND target_text_id = 520
ORDER BY source_domain, source_record_id;

-- Explicit available categories, excluding any semantic inference.
SELECT source_domain, category, evidence_grade, COUNT(*) AS edges
FROM verified_edges
GROUP BY source_domain, category, evidence_grade
ORDER BY edges DESC;

-- M3 resource identity and its byte-exact KIDSOBJDB native record count.
SELECT s.m3_record_id, s.name_hash, s.type_hash, s.source_bytes,
       COUNT(n.native_node_index) AS native_records
FROM native_sources AS s
LEFT JOIN m3_kidsobjdb_records AS n
 ON n.m3_record_id = s.m3_record_id
GROUP BY s.m3_record_id;

-- Object record with exact original byte boundaries; field semantics are
-- still UNKNOWN unless a compatible class property map was validated.
SELECT m3_record_id, native_node_index, record_start,
       record_byte_length, raw_u32_12, raw_u32_16, field_schema
FROM m3_kidsobjdb_records
WHERE m3_record_id = 'root:49334'
ORDER BY native_node_index
LIMIT 30;

-- If a raw integer equals an M7 table number, DO NOT treat it as a FK.
SELECT m3_record_id, byte_offset, observed_u32, possible_target_group,
       is_verified_fk
FROM unverified_candidates
WHERE is_verified_fk = 0
LIMIT 30;
