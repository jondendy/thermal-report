        """

    html_content += """
        </div>
    </body>
    </html>
    """

    with open("index.html", "w") as f:
        f.write(html_content)
    print("index.html successfully created.")

if __name__ == "__main__":
    run_thermal_processing()
    generate_index_html()
