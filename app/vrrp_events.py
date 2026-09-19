def classify_vrrp_event(old_master, new_master):
    """
    Klassifiziert einen bereits erkannten VRRP-Zustandswechsel.

    Priorität hat immer der neue Zustand:
      * MULTIPLE -> Split-Brain
      * NONE     -> kein MASTER
      * vorher MULTIPLE -> normalisiert
      * vorher NONE     -> Recovery
      * ansonsten       -> normaler MASTER-Wechsel
    """

    if new_master == 'MULTIPLE':
        return 'SPLIT_BRAIN'

    if new_master == 'NONE':
        return 'NO_MASTER'

    if old_master == 'MULTIPLE':
        return 'NORMALIZED'

    if old_master == 'NONE':
        return 'RECOVERY'

    return 'FAILOVER'


def is_vrrp_health_event(old_master, new_master):
    return classify_vrrp_event(
        old_master,
        new_master
    ) != 'FAILOVER'
