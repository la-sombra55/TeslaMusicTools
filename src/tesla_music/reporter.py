from pathlib import Path


def build_review_report(plan):
    lines = []

    lines.append("🚗 Tesla Music Tools - Change Review")
    lines.append("==================================")
    lines.append("")

    lines.append(
        f"Total proposed changes: {plan['total_changes']}"
    )

    lines.append("")

    current_group = None

    for change in plan["changes"]:
        group_key = (
            change["current_artist"],
            change["new_artist"],
        )

        if group_key != current_group:
            current_group = group_key

            lines.append("")
            lines.append("------------------------------")
            lines.append("")
            lines.append(
                f"Current artist: {change['current_artist']}"
            )
            lines.append(
                f"New artist: {change['new_artist']}"
            )
            lines.append(
                f"Confidence: {change['confidence']}% ({change['reason']})"
            )
            lines.append("")
            lines.append("Files:")

        file_line = f"  ✓ {Path(change['file']).name}"

        if change.get("new_title") and change["new_title"] != change.get("current_title"):
            file_line += (
                f' (Title: "{change["current_title"]}" → "{change["new_title"]}")'
            )

        lines.append(file_line)

    return "\n".join(lines)


def save_review_report(report, output_path):
    output_path = Path(output_path)

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as file:
        file.write(report)