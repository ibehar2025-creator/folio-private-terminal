import { useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { Panel, Field, Modal, Notice, Bars, n, dateLabel, Empty } from "../ui";
import type { Performance } from "../types";
import { useToast } from "../App";

export function PerformanceDetails({ data }: { data: Performance }) {
  const [period, setPeriod] = useState("Weekly"),
    [open, setOpen] = useState(false),
    [error, setError] = useState("");
  const qc = useQueryClient(),
    toast = useToast();
  const chart =
    period === "Weekly"
      ? (data.weeks ?? []).map((r) => ({ name: r.week, value: n(r.return) }))
      : data.twr.daily.map((r) => ({ name: r.date, value: n(r.return) }));
  const save = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      await api(`/snapshots/${f.get("snapshot")}/flow`, "PUT", {
        external_flow: f.get("flow"),
        contributions: f.get("contributions") || null,
      });
      await qc.invalidateQueries();
      setOpen(false);
      toast("Cash-flow annotation saved");
    } catch (e) {
      setError((e as Error).message);
    }
  };
  return (
    <>
      <Panel
        title="Returns by observation period"
        action={
          <div className="segmented">
            {["Daily / observed", "Weekly"].map((p) => (
              <button
                key={p}
                className={period === p ? "selected" : ""}
                onClick={() => setPeriod(p)}
              >
                {p}
              </button>
            ))}
          </div>
        }
      >
        {chart.length ? (
          <Bars data={chart} percent />
        ) : (
          <Empty title="Verified cash flows are needed">
            Value changes alone cannot identify investment performance.
          </Empty>
        )}
        <button
          className="button"
          onClick={() => {
            setOpen(true);
            setError("");
          }}
          disabled={!data.snapshots.length}
        >
          Verify a cash-flow interval
        </button>
      </Panel>
      {open && (
        <Modal
          title="Verify external cash flows"
          onClose={() => setOpen(false)}
        >
          <Notice>
            Only enter a figure after reconciling the complete interval from the
            previous snapshot to the selected date. Deposits are positive,
            withdrawals negative. Enter zero only if you have verified there
            were no external flows. Transfers between tracked accounts are
            internal. This method assumes end-of-period flow timing.
          </Notice>
          <form onSubmit={save}>
            <Field label="Interval ending at snapshot">
              <select name="snapshot">
                {data.snapshots.slice(1).map((s) => (
                  <option key={s.id} value={s.id}>
                    {dateLabel(s.date)} · {s.source}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Verified net external flow ($)">
              <input name="flow" type="number" step=".01" required />
            </Field>
            <Field label="Cumulative net contributions (optional, $)">
              <input name="contributions" type="number" step=".01" />
            </Field>
            {error && <p className="form-error">{error}</p>}
            <button
              className="button primary"
              disabled={data.snapshots.length < 2}
            >
              Save verified flow
            </button>
          </form>
        </Modal>
      )}
    </>
  );
}
