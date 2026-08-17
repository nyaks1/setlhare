import difflib
import gzip
import json
import os
from huggingface_hub import HfApi, hf_hub_download

# Map display language names to search identifiers and default extensions
LANGUAGES = {
    "python": {"match": "python", "ext": "source.py"},
    "java": {"match": "java", "ext": "App.java"},
    "javascript": {"match": "javascript", "ext": "index.js"},
    "typescript": {"match": "typescript", "ext": "index.ts"},
    "c#": {"match": "c#", "ext": "Program.cs"},
    "cpp": {"match": "cpp", "ext": "main.cpp"},
    "rust": {"match": "rust", "ext": "main.rs"},
    "go": {"match": "go", "ext": "main.go"},
    "shell": {"match": "shell", "ext": "script.sh"},
}


def make_diff(old_code: str, new_code: str, filename: str) -> str:
  """Generates unified git diff format."""
  old_lines = old_code.splitlines(keepends=True)
  new_lines = new_code.splitlines(keepends=True)
  diff = difflib.unified_diff(
      old_lines, new_lines, fromfile=f"a/{filename}", tofile=f"b/{filename}"
  )
  return "".join(diff)


def stream_repo_file(repo_id: str, filename: str):
  """Downloads the specific shard to local cache and yields parsed JSON objects."""
  local_path = hf_hub_download(
      repo_id=repo_id,
      filename=filename,
      repo_type="dataset",
      token=os.getenv("HF_TOKEN"),
  )

  if local_path.endswith(".gz"):
    with gzip.open(local_path, "rt", encoding="utf-8", errors="replace") as f:
      for line in f:
        if line.strip():
          yield json.loads(line)
  else:
    with open(local_path, "r", encoding="utf-8", errors="replace") as f:
      for line in f:
        if line.strip():
          yield json.loads(line)


def generate_multilingual_dataset(
    output_path="data/setlhare_train.jsonl", samples_per_lang=500
):
  os.makedirs(os.path.dirname(output_path), exist_ok=True)
  api = HfApi()
  repo_id = "bigcode/commitpackft"

  print("[Setlhare] Fetching dataset file tree from Hugging Face...")
  repo_files = api.list_repo_files(repo_id=repo_id, repo_type="dataset")

  all_samples = []

  for lang_name, meta in LANGUAGES.items():
    print(f"[Setlhare] Extracting {lang_name} examples...")
    target_match = meta["match"].lower()
    default_ext = meta["ext"]

    # Match files matching the language partition (e.g. data/python/..., python.jsonl.gz, etc.)
    matched_files = [
        f
        for f in repo_files
        if target_match in f.lower() and (f.endswith(".jsonl") or f.endswith(".jsonl.gz"))
    ]

    if not matched_files:
      print(f"[Warning] No data files found for {lang_name}")
      continue

    count = 0
    for repo_file in matched_files:
      try:
        for item in stream_repo_file(repo_id, repo_file):
          subject = item.get("subject", "").strip()
          old_code = item.get("old_contents", "").strip()
          new_code = item.get("new_contents", "").strip()
          filename = item.get("old_file") or default_ext

          # Quality filtering
          if not old_code or not new_code or old_code == new_code:
            continue
          if (
              len(old_code) > 2500
              or len(new_code) > 2500
              or len(old_code) < 30
          ):
            continue

          diff = make_diff(old_code, new_code, filename)
          if not diff:
            continue

          user_prompt = (
              f"### LANGUAGE:\n{lang_name.upper()}\n\n"
              f"### ISSUE / TASK:\n{subject}\n\n"
              f"### LOCAL CODE CONTEXT:\nFile: {filename}\n{old_code}"
          )
          assistant_response = (
              f"### ROOT CAUSE DIAGNOSIS:\nFix applied to address:"
              f" {subject}\n\n### GIT DIFF PATCH:\n```diff\n{diff}```\n\n###"
              f" EXPLANATION:\nUpdated {filename} to implement the required"
              " correction."
          )

          messages = [
              {
                  "role": "system",
                  "content": (
                      "You are Setlhare, an offline terminal pair programmer."
                      " Given a task/error and local codebase context, diagnose"
                      " the issue, generate a unified Git diff patch, and"
                      " explain the fix."
                  ),
              },
              {"role": "user", "content": user_prompt},
              {"role": "assistant", "content": assistant_response},
          ]

          all_samples.append({"messages": messages})
          count += 1
          if count >= samples_per_lang:
            break

        if count >= samples_per_lang:
          break
      except Exception as e:
        print(f"[Warning] Error processing file {repo_file}: {e}")

    print(f"[Setlhare] Collected {count} samples for {lang_name}.")

  with open(output_path, "w", encoding="utf-8") as f:
    for entry in all_samples:
      f.write(json.dumps(entry) + "\n")

  print(
      f"\n[Setlhare] Finished! Saved {len(all_samples)} multi-language samples"
      f" to {output_path}"
  )


if __name__ == "__main__":
  generate_multilingual_dataset()