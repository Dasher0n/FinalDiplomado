import { ComponentFixture, TestBed } from "@angular/core/testing";

import { App } from "./app";

describe("App", () => {
  let fixture: ComponentFixture<App>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
    }).compileComponents();

    fixture = TestBed.createComponent(App);
    fixture.detectChanges();
  });

  it("muestra la marca de la aplicacion", () => {
    expect(fixture.nativeElement.textContent).toContain("Wise Dice");
  });
});
