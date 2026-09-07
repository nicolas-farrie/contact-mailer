#!/bin/sh
# Installe les hooks git locaux du projet (non versionnés par git : .git/hooks/).
#
# Seul hook posé : la régénération de .version après chaque commit, changement de
# branche ou merge. Le conteneur n'embarque pas git — sans ce fichier il ne peut pas
# afficher le tag (cf. config.py, Makefile version-file).
#
#   Usage :  sh tools/install-git-hooks.sh
set -e

root=$(git rev-parse --show-toplevel)
hooks="$root/.git/hooks"

for name in post-commit post-checkout post-merge; do
    cat > "$hooks/$name" <<'HOOK'
#!/bin/sh
# Régénère .version — installé par tools/install-git-hooks.sh. Même format que la
# cible Makefile `version-file` : ligne 1 = git describe, ligne 2 = SHA de HEAD.
root=$(git rev-parse --show-toplevel) || exit 0
printf '%s\n%s\n' \
    "$(git -C "$root" describe --tags --always --dirty 2>/dev/null || echo dev)" \
    "$(git -C "$root" rev-parse --short HEAD 2>/dev/null || echo '')" \
    > "$root/.version"
HOOK
    chmod +x "$hooks/$name"
    echo "installé : .git/hooks/$name"
done

# Premier remplissage, pour ne pas attendre le prochain commit.
make -C "$root" version-file
echo "à jour : $(head -1 "$root/.version")"
