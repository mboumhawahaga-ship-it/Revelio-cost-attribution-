def _extract_resource_id(event: dict) -> str | None:
    name = event.get("eventName", "")
    resp = event.get("responseElements") or {}
    req = event.get("requestParameters") or {}

    if name == "RunInstances":
        items = resp.get("instancesSet", {}).get("items", [])
        if items:
            return items[0].get("instanceId")

    if name == "PutObject":
        bucket = req.get("bucketName")
        return f"arn:aws:s3:::{bucket}" if bucket else None

    if name == "CreateDBInstance":
        return resp.get("dBInstanceArn")

    if name == "Invoke":
        func = req.get("functionName")
        # match the ARN prefix used in CUR
        return f"arn:aws:lambda:eu-west-1:123456789012:function:{func}" if func else None

    return None


def build_resource_index(cloudtrail_records: list[dict]) -> dict[str, str]:
    """Returns {resource_id: username}."""
    index = {}
    for event in cloudtrail_records:
        resource_id = _extract_resource_id(event)
        if resource_id:
            user = event.get("userIdentity", {}).get("userName", "unknown")
            index[resource_id] = user
    return index


def correlate(cur_rows: list[dict], cloudtrail_records: list[dict]) -> list[dict]:
    index = build_resource_index(cloudtrail_records)
    enriched = []
    for row in cur_rows:
        resource_id = row.get("lineItem/ResourceId", "")
        enriched.append({
            "resource_id": resource_id,
            "service": row.get("lineItem/ProductCode"),
            "operation": row.get("lineItem/Operation"),
            "usage_start": row.get("lineItem/UsageStartDate"),
            "usage_amount": float(row.get("lineItem/UsageAmount", 0)),
            "cost_usd": float(row.get("lineItem/UnblendedCost", 0)),
            "initiated_by": index.get(resource_id, "not-found-in-cloudtrail"),
        })
    return enriched
