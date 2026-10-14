"""Accounting checks: a retained aggregate count must not hide TP identity loss."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('release_compare', Path(__file__).with_name('compare.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def row(rule, description, label='tp'):
    return {'path': '/fixture', 'identity': [rule, 'system_prompt', 1, description, ''],
            'id': description, 'label': label}


def manifest(rows):
    return {'references': rows, 'files': [{'path': '/fixture'}],
            'seed_sha256': 'fixture', 'seed_labels': {'tp': len(rows)}}


def test_equal_counts_cannot_hide_replaced_tp():
    original, replacement = row('H4', 'original'), row('H4', 'replacement')
    replacement['identity'][-1] = 'different evidence'
    report, private = module.compare(manifest([original]), [original], [replacement])
    assert report['status'] == 'BLOCKED'
    assert report['non_h6_tp_losses'] == 1
    assert private['lost_tp_ids'] == ['original']


def test_diagnostic_wording_change_preserves_stable_identity():
    original, reworded = row('H4', 'original'), row('H4', 'reworded')
    report, private = module.compare(manifest([original]), [original], [reworded])
    assert report['status'] == 'PASS_REFERENCE_TP_RETENTION'
    assert report['non_h6_tp_losses'] == 0
    assert report['by_rule']['H4']['diagnostic_wording_changed'] == 1
    assert private['exact_text_changed_tp_ids'] == ['original']


def test_missing_baseline_reference_blocks():
    original = row('H4', 'original')
    report, _ = module.compare(manifest([original]), [], [])
    assert report['status'] == 'BLOCKED'
    assert report['reference_tp_missing_from_baseline'] == 1


def test_h6_retirement_is_separate_and_unknown_loss_visible():
    retired, unknown = row('H6', 'retired'), row('H4', 'unknown')
    report, _ = module.compare(manifest([retired]), [retired, unknown], [])
    assert report['non_h6_tp_losses'] == 0
    assert report['h6_separate']['lost_tp'] == 1
    assert report['by_rule']['H4']['removed_unknown'] == 1


def test_gate_delivery_is_exact_and_labeled_decisions_are_counted():
    tp = row('H1.8', 'retained true positive')
    fp = row('H4.5', 'retained false positive', 'fp')
    reworded_tp = row('H1.8', 'new diagnostic prose')
    gated = [dict(reworded_tp, gate_decision='KEEP', gate_probability=0.9, severity='high'),
             dict(fp, gate_decision='DISMISS', gate_probability=0.1, severity='high')]
    report = module.gate_summary([reworded_tp, fp], gated, [tp, fp])
    assert report['status'] == 'PASS_ANNOTATION_ONLY'
    assert report['decisions'] == {'KEEP': 1, 'DISMISS': 1}
    assert report['by_reference_label']['tp'] == {'KEEP': 1}
    assert report['by_reference_label']['fp'] == {'DISMISS': 1}


def test_gate_delivery_rejects_suppressed_finding():
    tp = row('H1.8', 'retained true positive')
    try:
        module.gate_summary([tp], [], [tp])
    except ValueError as error:
        assert 'Gate changed delivered detector finding identities' in str(error)
    else:
        raise AssertionError('Suppression was accepted')


def test_muse_default_gate_counts_suppressed_tp():
    tp = row('H4', 'true positive')
    fp = row('H4', 'false positive', 'fp')
    fp['identity'][-1] = 'other evidence'
    report = module.native_gate_summary([tp, fp], [dict(fp, gate_decision='KEEP')], [tp, fp])
    assert report['suppressed'] == 1
    assert report['suppressed_by_reference_label'] == {'tp': 1}
