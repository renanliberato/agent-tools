#!/usr/bin/env bash
set -u

applydiff() {
  local target_dir
  local patch_file
  local common_git_dir

  common_git_dir="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" || {
    echo "erro: nao estou dentro de um repositorio git"
    return 1
  }

  target_dir="$(dirname "$common_git_dir")"

  if [[ ! -d "$target_dir" ]]; then
    echo "erro: nao consegui localizar a pasta do repositorio principal: $target_dir"
    return 1
  fi

  patch_file="$(mktemp /tmp/gitdiff.XXXXXX.patch)" || return 1

  # diff de arquivos modificados
  if ! git diff > "$patch_file"; then
    echo "erro: nao consegui gerar o patch"
    rm -f "$patch_file"
    return 1
  fi

  # incluir arquivos novos (untracked)
  while IFS= read -r file; do
    git diff --no-index /dev/null "$file" >> "$patch_file"
  done < <(git ls-files --others --exclude-standard)

  if [[ ! -s "$patch_file" ]]; then
    echo "nenhuma diferenca para aplicar"
    rm -f "$patch_file"
    return 0
  fi

  if (cd "$target_dir" && git apply "$patch_file"); then
    echo "patch aplicado em: $target_dir"
    rm -f "$patch_file"
  else
    echo "erro: falha ao aplicar patch em: $target_dir"
    echo "patch mantido em: $patch_file"
    return 1
  fi
}

applydiff "$@"
