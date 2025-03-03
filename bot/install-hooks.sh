#!/bin/bash

# Script to install git hooks for the bot

# Create pre-commit hook content
cat > ../.git/hooks/pre-commit << 'EOL'
#!/bin/bash

# Only allow changes in src/bot_gen
allowed_prefix="src/bot_gen/"
error=0

# Get list of staged files
staged_files=$(git diff --cached --name-only)

# Check each staged file
for file in $staged_files; do
    if [[ ! $file =~ ^$allowed_prefix ]]; then
        echo "Error: Cannot commit '$file'"
        echo "Only files in $allowed_prefix are allowed"
        error=1
    fi
done

if [ $error -ne 0 ]; then
    echo "Commit aborted: Attempted to modify files outside of $allowed_prefix"
    exit 1
fi

exit 0
EOL

# Make the hook executable
chmod +x ../.git/hooks/pre-commit

# Set up sparse-checkout
git config core.sparseCheckout true
mkdir -p ../.git/info
echo "src/bot_gen/" > ../.git/info/sparse-checkout

echo "Git hooks installed successfully!"
echo "Pre-commit hook will only allow changes in src/bot_gen/"
echo "Sparse-checkout configured to focus on src/bot_gen/"