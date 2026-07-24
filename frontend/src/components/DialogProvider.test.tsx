import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { DialogProvider, useDialogs } from "./DialogProvider";

function Harness() {
  const dialogs = useDialogs();
  const [result, setResult] = useState("");
  return (
    <>
      <button
        onClick={() =>
          void dialogs
            .prompt({
              title: "編輯建議",
              message: "請更新內容",
              initialValue: "原內容",
            })
            .then((value) => setResult(value ?? "cancelled"))
        }
      >
        open
      </button>
      <output>{result}</output>
    </>
  );
}

describe("DialogProvider", () => {
  it("returns text submitted through the custom dialog", async () => {
    render(
      <DialogProvider>
        <Harness />
      </DialogProvider>,
    );
    fireEvent.click(screen.getByText("open"));
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "更新內容" },
    });
    fireEvent.click(screen.getByText("確認"));
    expect(await screen.findByText("更新內容")).toBeInTheDocument();
  });
});
