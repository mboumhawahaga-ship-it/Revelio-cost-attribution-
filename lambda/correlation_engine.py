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
        if not func:
            return None
        # Cherche l'ARN exact dans le CUR plutôt que de le hardcoder
        # Le CUR contient : arn:aws:lambda:<region>:<account>:function:<name>
        # On retourne juste le nom de fonction pour matcher via endswith
        return func

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

        # Lookup direct d'abord
        owner = index.get(resource_id)

        # Fallback : si resource_id est un ARN Lambda, on cherche par nom de fonction
        # CUR stocke : arn:aws:lambda:<region>:<account>:function:<name>
        # CloudTrail stocke : juste le nom de la fonction
        if owner is None and ":function:" in resource_id:
            func_name = resource_id.split(":function:")[-1]
            owner = index.get(func_name)

        enriched.append({
            "resource_id": resource_id,
            "service": row.get("lineItem/ProductCode"),
            "operation": row.get("lineItem/Operation"),
            "usage_start": row.get("lineItem/UsageStartDate"),
            "usage_amount": float(row.get("lineItem/UsageAmount", 0)),
            "cost_usd": float(row.get("lineItem/UnblendedCost", 0)),
            "initiated_by": owner or "not-found-in-cloudtrail",
        })
    return enriched
