/*
 * What the panel's main button should say, and what pressing it should do.
 *
 * This is a decision, not a rendering, so it lives on its own where it can be
 * tested without a panel around it. The button is the only thing most people
 * ever press; getting its order wrong means the tool quietly does nothing,
 * which is exactly what happened when asking came before filling.
 */
(function (root) {
  "use strict";

  /**
   * @param {object} view
   * @param {object|null} view.observation  the last scan
   * @param {object|null} view.plan         the last plan
   * @param {number} view.outstanding       required questions still unanswered
   * @param {string} view.submissionPolicy  "auto" or anything else
   * @returns {{label: string, note: string, action: string, disabled: boolean}}
   */
  function decide(view) {
    const observation = view.observation || null;
    const plan = view.plan || null;
    const outstanding = Number(view.outstanding) || 0;
    const actions = (plan && plan.actions) || [];
    const next = ((observation || {}).next_controls || [])[0];
    const submit = ((observation || {}).submit_controls || [])[0];

    if (!observation) {
      return { label: "Scan this page", note: "", action: "scan", disabled: false };
    }

    const apply = (observation.apply_controls || [])[0];

    // A job description with an Apply button on it.
    //
    // Nothing here ever pressed one, and the button said "Scan this page" --
    // which scanned, found the same nothing, and said it again. A dead end on
    // 58 of 125 real job URLs, including every one served by one large ATS.
    // The form was always a click away and nobody was ever offered the click.
    //
    // Below filling, so a page with fields to fill is never navigated away
    // from, and only when this is not already an application: plenty of forms
    // carry an "Apply" control that is their own submit.
    if (
      apply &&
      observation.kind !== "application" &&
      actions.length === 0 &&
      outstanding === 0
    ) {
      return {
        label: "Open the application ▸",
        note: `Presses "${apply.text}". Nothing is sent by opening a form.`,
        action: "apply",
        disabled: false,
      };
    }

    if ((observation.fields || []).length === 0) {
      return { label: "Scan this page", note: "", action: "scan", disabled: false };
    }

    // Filling comes before asking, always.
    //
    // This used to be the other way round: any outstanding required question
    // turned the button into a scroll-to-the-question and the plan's ready
    // actions were never carried out, under a note reading "I have filled
    // everything else I can" when nothing had been filled at all. On a page
    // holding a required question that can never be answered -- "Login" on a
    // form that wants an account, which this tool refuses to create on
    // purpose -- outstanding never reached zero, so the button never came back
    // and the form was never filled. Twenty-two fields with answers waiting
    // sat under a heading that read "Completed (0)".
    //
    // Actions and questions cover disjoint fields, so holding one back for the
    // other buys nothing.
    if (actions.length) {
      return {
        label: "Fill this page",
        note:
          `${actions.length} field(s) I can fill from what you saved.` +
          (outstanding ? ` Then ${outstanding} question(s) for you.` : ""),
        action: "fill",
        disabled: false,
      };
    }

    if (outstanding) {
      return {
        label: `Answer ${outstanding} question${outstanding > 1 ? "s" : ""}`,
        note: "I have filled everything else I can.",
        action: "focus",
        disabled: false,
      };
    }

    if (next) {
      return {
        label: "Continue application ▸",
        note: `Presses "${next.text}".`,
        action: "next",
        disabled: false,
      };
    }

    if (submit) {
      if (view.submissionPolicy === "auto") {
        return {
          label: "Submit application ▸",
          note: "You set submitting to happen automatically.",
          action: "submit",
          disabled: false,
        };
      }
      return {
        label: `Press "${submit.text}" yourself`,
        note: "I do not press final submit. Change that in Settings if you want to.",
        action: "none",
        disabled: true,
      };
    }

    return { label: "Rescan this page", note: "", action: "scan", disabled: false };
  }

  root.ApplyPilotCta = { decide: decide };
})(typeof globalThis !== "undefined" ? globalThis : this);
