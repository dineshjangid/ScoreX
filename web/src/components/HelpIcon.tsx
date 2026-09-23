interface Props {
  text: string;
}

/** A small "?" badge that highlights and shows a tooltip on hover —
 * pure CSS (attr(data-tooltip) content), no JS state needed. */
export default function HelpIcon({ text }: Props) {
  return (
    <span className="help-icon" data-tooltip={text} tabIndex={0}>
      ?
    </span>
  );
}
