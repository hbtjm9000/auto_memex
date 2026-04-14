#!/bin/bash
# LLM-Wiki Worker - Processes content_queue.json tasks
# Saves to ~/Riki/Utils/worker.sh

QUEUE_FILE='/home/hbtjm/library/content_queue.json'
LIBRARY_DIR='/home/hbtjm/library'
INDEX_FILE="$LIBRARY_DIR/index.md"
LOG_FILE="$LIBRARY_DIR/log.md"

exec >> /home/hbtjm/library/worker.log 2>&1

TODAY=$(date +%Y-%m-%d)

# Load queue_manager for helper functions
QUEUE_MANAGER='/home/hbtjm/library/queue_manager.py'

get_task() {
    python "$QUEUE_MANAGER" pop
}

mark_done() {
    python "$QUEUE_MANAGER" complete "$1"
}

update_index() {
    local page_name="$1"
    local page_type="$2"
    local section=""
    
    case "$page_type" in
        entity) section="Entities" ;;
        concept) section="Concepts" ;;
        comparison) section="Comparisons" ;;
        query) section="Queries" ;;
        *) section="Concepts" ;;
    esac
    
    # Add to index if not already present
    if ! grep -q "[[$page_name]]" "$INDEX_FILE" 2>/dev/null; then
        # Find section and add after it (before next section)
        sed -i "/^## $section$/a\\\\n- [[$page_name]]" "$INDEX_FILE"
    fi
}

append_log() {
    local page_title="$1"
    echo -e "## [$TODAY] ingest | $page_title" >> "$LOG_FILE"
}

normalize_filename() {
    local name="$1"
    # Lowercase
    name=$(echo "$name" | tr '[:upper:]' '[:lower:]')
    # Spaces to hyphens
    name="${name// /-}"
    # & to "and"
    name="${name//&/and}"
    # ; and other special chars removed
    name=$(echo "$name" | tr -cd 'a-z0-9-.')
    # Remove leading/trailing hyphens
    name="${name##-}"
    name="${name%%-}"
    # Collapse multiple hyphens to single
    name=$(echo "$name" | sed 's/-\+/-/g')
    echo "$name"
}

process_youtube() {
    local url="$1"
    local title="$2"
    local page_name="$3"
    local task_type="$4"
    local sources="$5"
    local influencer="$6"
    
    # Fetch transcript via youtube_content skill
    TRANSCRIPT=$(python -c "
from skills import skill_view
try:
    content = skill_view('youtube-content')
    print(content)
except:
    print('')
" 2>/dev/null)
    
    # Build prompt for YouTube processing
    PROMPT="You are an ingestion worker for an IT wiki.

**Task**: Create or update a wiki page from a YouTube video.

**Source URL**: $url
**Page Name**: $page_name
**Type**: $task_type
**Influencer**: $influencer

**Instructions**:
1. Fetch the YouTube transcript using the youtube-subtitling tool
2. Extract key IT/Tech concepts from the transcript
3. Create/update the page at $LIBRARY_DIR/$page_name.md (the .md extension is added automatically by the system — do NOT add .md to the path yourself) with:
   - STRICT frontmatter (YAML): title, created: $TODAY, updated: $TODAY, type: $task_type, tags (use SCHEMA.md taxonomy), sources: [$sources]
   - Substantive content (50+ words) explaining the concepts
   - At least 2 wikilinks to existing wiki pages
   - The page title in frontmatter must match '$title'

4. After creating the page:
   - Update $INDEX_FILE: add '- [[$page_name]] ...' in the correct section
   - Append to $LOG_FILE: '## [$TODAY] ingest | $title'

5. Verify the created file has valid frontmatter before completing.

Do not apologize. Execute the file writes now."
}

process_url() {
    local url="$1"
    local title="$2"
    local page_name="$3"
    local task_type="$4"
    local sources="$5"
    local influencer="$6"
    
    # Check if page already exists
    local page_path="$LIBRARY_DIR/$page_name.md"
    local action="create"
    if [ -f "$page_path" ]; then
        action="update"
    fi
    
    # Build prompt for URL processing
    PROMPT="You are an ingestion worker for an IT wiki.

**Task**: $action a wiki page from a web URL.

**Source URL**: $url
**Page Name**: $page_name
**Type**: $task_type
**Influencer**: $influencer
**Action**: $action

**Instructions**:
1. Fetch content from the URL using web_extract tool
2. Extract key IT/Tech concepts from the content
3. $action/update the page at $LIBRARY_DIR/$page_name.md (the .md extension is added automatically by the system — do NOT add .md to the path yourself) with:
   - STRICT frontmatter (YAML): title, created: $TODAY, updated: $TODAY, type: $task_type, tags (use SCHEMA.md taxonomy), sources: [$sources]
   - Substantive content (50+ words) explaining the concepts
   - At least 2 wikilinks to existing wiki pages
   - The page title in frontmatter must match '$title'

4. After creating/updating the page:
   - Update $INDEX_FILE: add '- [[$page_name]] ...' in the correct section
   - Append to $LOG_FILE: '## [$TODAY] ingest | $title'

5. Verify the created file has valid frontmatter before completing.

Do not apologize. Execute the file writes now."
}

process_task() {
    local task_json="$1"
    
    # Parse task fields
    local id=$(echo "$task_json" | grep -o '"id": "[^"]*"' | cut -d'"' -f4)
    local url=$(echo "$task_json" | grep -o '"url": "[^"]*"' | cut -d'"' -f4)
    local title=$(echo "$task_json" | grep -o '"title": "[^"]*"' | cut -d'"' -f4)
    local task_type=$(echo "$task_json" | grep -o '"type": "[^"]*"' | cut -d'"' -f4)
    local influencer=$(echo "$task_json" | grep -o '"influencer": "[^"]*"' | cut -d'"' -f4)
    local is_youtube=$(echo "$task_json" | grep -o '"youtube": true' | cut -d':' -f2)
    
    echo "Processing Task $id: $title (type: $task_type)"
    
    # Normalize filename
    local page_name=$(normalize_filename "$title")
    # Determine subdirectory based on type
    local subdir="concepts"
    case "$task_type" in
        entity) subdir="entities" ;;
        comparison) subdir="comparisons" ;;
        query) subdir="queries" ;;
    esac
    local page_name="$subdir/$page_name"
    
    # Build sources URL
    local sources="$url"
    
    # Process based on URL type
    if [ "$is_youtube" = "true" ] || echo "$url" | grep -q "youtube.com\|youtu.be"; then
        process_youtube "$url" "$title" "$page_name" "$task_type" "$sources" "$influencer"
    else
        process_url "$url" "$title" "$page_name" "$task_type" "$sources" "$influencer"
    fi
    
    # Call hermes chat with the built prompt
    hermes chat -m gemini-2.5-flash -t terminal,file,web -q "$PROMPT"
    
    # Mark task as done
    mark_done "$id"
    
    echo "Task $id completed."
}

# Main worker loop
echo "Worker started at $(date)"
while true; do
    TASK=$(get_task)
    
    if echo "$TASK" | grep -q '"error"'; then
        echo "Queue empty. Worker exiting."
        break
    fi
    
    if [ -n "$TASK" ]; then
        process_task "$TASK"
    fi
done

echo "Worker stopped at $(date)"
