from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
import typer

from .core import (
    DatasetSummary,
    compute_quality_flags,
    correlation_matrix,
    flatten_summary_for_print,
    missing_table,
    summarize_dataset,
    top_categories,
)
from .viz import (
    plot_correlation_heatmap,
    plot_missing_matrix,
    plot_histograms_per_column,
    save_top_categories_tables,
)

app = typer.Typer(help="Мини-CLI для EDA CSV-файлов")


def _load_csv(
    path: Path,
    sep: str = ",",
    encoding: str = "utf-8",
) -> pd.DataFrame:
    if not path.exists():
        raise typer.BadParameter(f"Файл '{path}' не найден")
    try:
        return pd.read_csv(path, sep=sep, encoding=encoding)
    except Exception as exc:  # noqa: BLE001
        raise typer.BadParameter(f"Не удалось прочитать CSV: {exc}") from exc


@app.command()
def overview(
    path: str = typer.Argument(..., help="Путь к CSV-файлу."),
    sep: str = typer.Option(",", help="Разделитель в CSV."),
    encoding: str = typer.Option("utf-8", help="Кодировка файла."),
) -> None:
    """
    Напечатать краткий обзор датасета:
    - размеры;
    - типы;
    - простая табличка по колонкам.
    """
    df = _load_csv(Path(path), sep=sep, encoding=encoding)
    summary: DatasetSummary = summarize_dataset(df)
    summary_df = flatten_summary_for_print(summary)

    typer.echo(f"Строк: {summary.n_rows}")
    typer.echo(f"Столбцов: {summary.n_cols}")
    typer.echo("\nКолонки:")
    typer.echo(summary_df.to_string(index=False))


@app.command()
def report(
    path: str = typer.Argument(..., help="Путь к CSV-файлу."),
    out_dir: str = typer.Option("reports", help="Каталог для отчёта."),
    sep: str = typer.Option(",", help="Разделитель в CSV."),
    encoding: str = typer.Option("utf-8", help="Кодировка файла."),
    max_hist_columns: int = typer.Option(6, help="Максимум числовых колонок для гистограмм."),
    max_cat_columns: int = typer.Option(5, help="Максимум категориальных колонок для анализа."),
    top_k_categories: int = typer.Option(5, help="Сколько top-значений выводить для категориальных признаков."),
    title: str = typer.Option("EDA-отчёт", help="Заголовок отчёта."),
    min_missing_share: float = typer.Option(0.3, help="Порог доли пропусков (0..1)."),
) -> None:
    """
    Сгенерировать полный EDA-отчёт:
    - текстовый overview и summary по колонкам (CSV/Markdown);
    - статистика пропусков;
    - корреляционная матрица;
    - top-k категорий по категориальным признакам;
    - картинки: гистограммы, матрица пропусков, heatmap корреляции.
    """
    if top_k_categories <= 0:
        raise typer.BadParameter("--top-k-categories должен быть > 0")
    if max_hist_columns <= 0:
        raise typer.BadParameter("--max-hist-columns должен быть > 0")
    if not (0.0 <= min_missing_share <= 1.0):
        raise typer.BadParameter("--min-missing-share должен быть в диапазоне [0..1]")

    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    df = _load_csv(Path(path), sep=sep, encoding=encoding)

    # 1. Обзор
    summary = summarize_dataset(df)
    summary_df = flatten_summary_for_print(summary)
    missing_df = missing_table(df)
    corr_df = correlation_matrix(df)

    # 2. Top-k категорий (пробуем передать параметр в core.py, если поддерживается)
    try:
        top_cats = top_categories(df, k=top_k_categories)  # если в core.py есть k
    except TypeError:
        # если core.top_categories не принимает k — режем результат здесь
        top_cats = top_categories(df)

    # подстрахуемся и ограничим top-k на стороне CLI в любом случае
    if isinstance(top_cats, dict):
        trimmed = {}
        for col, tbl in top_cats.items():
            try:
                trimmed[col] = tbl.head(top_k_categories)
            except Exception:
                trimmed[col] = tbl
        top_cats = trimmed

    # 3. Качество в целом
    quality_flags = compute_quality_flags(summary, missing_df)

    # 4. Проблемные колонки по пропускам (по новому порогу)
    problematic_missing = pd.DataFrame()
    if not missing_df.empty and "missing_share" in missing_df.columns:
        # missing_df у вас с index=имя колонки (судя по логике сохранения index=True)
        problematic_missing = missing_df[missing_df["missing_share"] >= float(min_missing_share)].copy()

    # 5. Сохраняем табличные артефакты
    summary_df.to_csv(out_root / "summary.csv", index=False)
    if not missing_df.empty:
        missing_df.to_csv(out_root / "missing.csv", index=True)
    if not corr_df.empty:
        corr_df.to_csv(out_root / "correlation.csv", index=True)
    save_top_categories_tables(top_cats, out_root / "top_categories")

    # 6. Markdown-отчёт
    md_path = out_root / "report.md"
    with md_path.open("w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n")
        f.write(f"Исходный файл: `{Path(path).name}`\n\n")
        f.write(f"Строк: **{summary.n_rows}**, столбцов: **{summary.n_cols}**\n\n")

        # Параметры отчёта 
        f.write("## Настройки отчёта\n\n")
        f.write(f"- max_hist_columns: **{max_hist_columns}**\n")
        f.write(f"- max_cat_columns: **{max_cat_columns}**\n")
        f.write(f"- top_k_categories: **{top_k_categories}**\n")
        f.write(f"- min_missing_share: **{min_missing_share:.2%}**\n\n")

        f.write("## Качество данных (эвристики)\n\n")
        f.write(f"- Оценка качества: **{quality_flags['quality_score']:.2f}**\n")
        f.write(f"- Макс. доля пропусков по колонке: **{quality_flags['max_missing_share']:.2%}**\n")
        f.write(f"- Слишком мало строк: **{quality_flags['too_few_rows']}**\n")
        f.write(f"- Слишком много колонок: **{quality_flags['too_many_columns']}**\n")
        f.write(f"- Слишком много пропусков: **{quality_flags['too_many_missing']}**\n")
        f.write(f"- Есть константные колонки: **{quality_flags['has_constant_columns']}**\n")
        f.write(
            f"- Есть категориальные признаки с высокой кардинальностью: "
            f"**{quality_flags['has_high_cardinality_categoricals']}**\n\n"
        )

        f.write("## Колонки\n\n")
        f.write("См. файл `summary.csv`.\n\n")

        f.write("## Пропуски\n\n")
        if missing_df.empty:
            f.write("Пропусков нет или датасет пуст.\n\n")
        else:
            f.write("См. файлы `missing.csv` и `missing_matrix.png`.\n\n")

            f.write(f"### Проблемные колонки (missing_share >= {min_missing_share:.2%})\n\n")
            if problematic_missing.empty:
                f.write("Проблемных колонок по заданному порогу не найдено.\n\n")
            else:
                f.write("Колонки:\n\n")
                for col_name, row in problematic_missing.iterrows():
                    ms = float(row["missing_share"])
                    mc = int(row["missing_count"])
                    f.write(f"- **{col_name}**: missing_count={mc}, missing_share={ms:.2%}\n")
                f.write("\n")

        f.write("## Корреляция числовых признаков\n\n")
        if corr_df.empty:
            f.write("Недостаточно числовых колонок для корреляции.\n\n")
        else:
            f.write("См. `correlation.csv` и `correlation_heatmap.png`.\n\n")

        f.write("## Категориальные признаки\n\n")
        if not top_cats:
            f.write("Категориальные/строковые признаки не найдены.\n\n")
        else:
            f.write(
                f"См. файлы в папке `top_categories/` "
                f"(макс. колонок: {max_cat_columns}, top-{top_k_categories} значений).\n\n"
            )

        f.write("## Гистограммы числовых колонок\n\n")
        f.write(f"См. файлы `hist_*.png` (максимум {max_hist_columns} колонок).\n")

    # 7. Картинки
    plot_histograms_per_column(df, out_root, max_columns=max_hist_columns)
    plot_missing_matrix(df, out_root / "missing_matrix.png")
    plot_correlation_heatmap(df, out_root / "correlation_heatmap.png")

    typer.echo(f"Отчёт сгенерирован в каталоге: {out_root}")
    typer.echo(f"- Основной markdown: {md_path}")
    typer.echo("- Табличные файлы: summary.csv, missing.csv, correlation.csv, top_categories/*.csv")
    typer.echo("- Графики: hist_*.png, missing_matrix.png, correlation_heatmap.png")


if __name__ == "__main__":
    app()
