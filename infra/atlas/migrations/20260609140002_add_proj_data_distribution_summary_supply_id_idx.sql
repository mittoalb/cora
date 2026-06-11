-- atlas:txmode none
-- Add supply_id index to proj_data_distribution_summary to support
-- reverse-lookup queries (list distributions per Supply for operator
-- decommission, Trust BC credential rotation, archive discovery).

CREATE INDEX IF NOT EXISTS proj_data_distribution_summary_supply_id_idx
    ON proj_data_distribution_summary (supply_id);
